#include <stdio.h>
#include <limits.h>
#include <unistd.h>

#include <epicsTime.h>
#include <epicsExit.h>
#include <epicsEvent.h>

#include "server.h"
#include "utils.h"

#include "ADExternalPlugin.h"


#define SERVER_POLL_TIMEOUT_MS 1000


struct shared_mem_context *_global_shared_mem = NULL;


static void *new_frame_malloc(size_t size)
{
    return shared_mem_malloc(_global_shared_mem, size);
}


static void new_frame_free(void *ptr)
{
    shared_mem_free(_global_shared_mem, ptr);
}


static void _com_task(void *arg)
{
    ADExternalPlugin *extPlugin = (ADExternalPlugin *) arg;
    extPlugin->comTask();
}


static void _shutdown(void *arg)
{
    ADExternalPlugin *extPlugin = (ADExternalPlugin *) arg;
    extPlugin->shutdown();
}


// Used in error printing
static const char *driverName = "ADExternalPlugin";


ADExternalPlugin::ADExternalPlugin(
    const char *portNameArg, const char *socketPath, const char *shmName,
    const char *className, int queueSize, int blockingCallbacks,
    const char *NDArrayPort, int NDArrayAddr, size_t maxMemory,
    int priority, int stackSize)
    : NDPluginDriver(portNameArg, queueSize,
        blockingCallbacks, NDArrayPort, NDArrayAddr, 1, 0, maxMemory,
        asynGenericPointerMask|asynFloat64ArrayMask,
        asynGenericPointerMask|asynFloat64ArrayMask, 0, 1,
        priority, stackSize, 1), shmName(shmName), className(className),
        nextParam(0)
{
    server = server_create(socketPath);
    if (!server) {
        ASYN_ERROR("%s: Failed to create server\n", driverName);
        return;
    }

    if (_global_shared_mem) {
        ASYN_FLOW("%s: using already created shared memory\n", driverName);
        /* we are assuming initialization is serialised, it is true now, but
         * might change in future */
        shmem = _global_shared_mem;
    } else {
        shmem = shared_mem_create(shmName, maxMemory);
        if (!shmem) {
            ASYN_ERROR("%s: Failed to create shared memory\n", driverName);
            return;
        }
        _global_shared_mem = shmem;
        NDArrayPool::setDefaultFrameMemoryFunctions(
            new_frame_malloc, new_frame_free);
    }
    setStringParam(NDPluginDriverPluginType, "ADExternalPlugin");
    createParam("WORKERSNUM", asynParamInt32, &workersNumParam);
    createParam("CLASSNAME", asynParamOctet, &classNameParam);
    createParam("PROCTIME", asynParamFloat64, &procTimeParam);
    setIntegerParam(workersNumParam, 0);
    setStringParam(classNameParam, className);
    setDoubleParam(procTimeParam, 0.0);
    callParamCallbacks();
    workersMutex = epicsMutexMustCreate();
    hasWorker = epicsEventMustCreate(epicsEventEmpty);
    epicsThreadCreate(
        "comthread", epicsThreadPriorityMedium,
        epicsThreadGetStackSize(epicsThreadStackMedium), _com_task, this);
    epicsAtExit(_shutdown, this);
    connectToArrayPort();
}


void ADExternalPlugin::shutdown()
{
    if (_global_shared_mem) {
        /* we are assuming shutdown is serialised, it is true now, but might
         * change in future */
        shared_mem_destroy(shmem);
        _global_shared_mem = NULL;
    }
    server_destroy(server);
}


void ADExternalPlugin::_initialise_new_connection(struct server_connection *con)
{
    struct worker_context *context =
        (struct worker_context *) malloc(sizeof(struct worker_context));
    server_connection_set_private(con, context);
    context->state = WORKER_HANDSHAKE;
    context->con = con;
    context->sock = server_connection_get_socket(con);
    context->frame = NULL;
}


void ADExternalPlugin::_destroy_connection(struct server_connection *con)
{
    struct worker_context *context =
        (struct worker_context *) server_connection_get_private(con);
    int droppedArrays;
    epicsMutexLock(workersMutex);
    workers.erase(context);
    epicsMutexUnlock(workersMutex);
    this->lock();
    setIntegerParam(workersNumParam, workers.size());
    if (context->frame) {
        getIntegerParam(NDPluginDriverDroppedArrays, &droppedArrays);
        ASYN_ERROR("%s: dropped frame %d because worker died in action\n",
           driverName, context->frame->uniqueId);
        droppedArrays++;
        setIntegerParam(NDPluginDriverDroppedArrays, droppedArrays);
        context->frame->release();
    }
    callParamCallbacks();
    this->unlock();
    free(context);
}


void ADExternalPlugin::_process_working_worker_message(
    struct worker_context *worker, rapidjson::Document &data)
{
    // Update parameters
    rapidjson::Value::MemberIterator it = data.FindMember("vars");
    if (it != data.MemberEnd() && it->value.IsObject())
        _update_parameters(it->value);

    it = data.FindMember("push_frame");
    if (it == data.MemberEnd() || !it->value.IsBool())
        return;

    NDArray *pArray = worker->frame;
    if (it->value.GetBool() && pArray) {
        it = data.FindMember("frame_dims");
        if (it != data.MemberEnd() && it->value.IsArray()) {
            int index = 0;
            for (auto &dim_val : it->value.GetArray()) {
                if (dim_val.IsInt() &&
                        (size_t) dim_val.GetInt() <= pArray->dims[index].size)
                    pArray->dims[index++].size = (size_t) dim_val.GetInt();
            }
        }
        it = data.FindMember("data_type");
        if (it != data.MemberEnd() && it->value.IsString()) {
            pArray->dataType = ad_data_type_from_string(it->value.GetString());
        }

        it = data.FindMember("attrs");
        if (it != data.MemberEnd() && it->value.IsObject())
            _populate_attrs_in_frame(it->value, pArray);

        // Calling endProcessCallbacks(without errors) forces us to copy the
        // frame, which we don't want to
        doCallbacksGenericPointer(pArray, NDArrayData, 0);
        callParamCallbacks();
    }
    if (pArray)
        pArray->release();

    worker->frame = NULL;
    epicsTimeStamp ts_end;
    epicsTimeGetCurrent(&ts_end);
    this->lock();
    setDoubleParam(
        procTimeParam,
        epicsTimeDiffInSeconds(&ts_end, &worker->ts_start) * 1000);
    callParamCallbacks();
    this->unlock();
    epicsEventSignal(hasWorker);
}


void ADExternalPlugin::_process_worker_message(
    struct worker_context *worker, rapidjson::Document &data)
{
    switch (worker->state) {
        case WORKER_HANDSHAKE:
            _process_handshake_worker_message(worker, data);
            break;
        case WORKER_WORKING:
            _process_working_worker_message(worker, data);
            break;
        default:
            ASYN_ERROR("%s: Worker state got corrupted, closing connection\n",
                driverName);
            server_connection_close(worker->con);
            break;
    }
}


void ADExternalPlugin::_handle_server_events()
{
    for (;;) {
        ssize_t rc;
        struct server_connection_event event = server_pop_event(server);
        if (event.type == SCONNECTION_EVENT_NONE)
              break;

        int sock = server_connection_get_socket(event.connection);

        switch (event.type) {
            case SCONNECTION_EVENT_CREATE:
                _initialise_new_connection(event.connection);
                break;
            case SCONNECTION_EVENT_IN:
                rc = read(sock, this->msgBuffer, MAX_MSG_SIZE);
                if (rc > 0) {
                    msgBuffer[rc] = 0;
                    rapidjson::Document doc;
                    doc.ParseInsitu(this->msgBuffer);
                    if (doc.HasParseError() || !doc.IsObject()) {
                        ASYN_ERROR("%s: Error parsing message\n", driverName);
                        // gibberish! we can't rely on this worker anymore
                        server_connection_close(event.connection);
                    } else {
                        struct worker_context *worker =
                            (struct worker_context *)
                                server_connection_get_private(event.connection);
                        _process_worker_message(worker, doc);
                    }
                } else if (rc == 0) {
                    server_connection_close(event.connection);
                } else {
                    ASYN_ERROR("%s: unix socket read error %ld\n",
                        driverName, rc);
                }
                break;
            case SCONNECTION_EVENT_CLOSED:
                _destroy_connection(event.connection);
                server_connection_destroy(event.connection);
                break;
            default:
                break;
        }
    }
}


void ADExternalPlugin::comTask()
{
    while (true) {
        server_poll(server, SERVER_POLL_TIMEOUT_MS);
        _handle_server_events();
    }
}


asynStatus ADExternalPlugin::drvUserCreate(
    asynUser *pasynUser, const char *drvInfo, const char **pptypeName,
    size_t *psize)
{
    int param;
    if (findParam(drvInfo, &param) != asynSuccess) {
        if (nextParam >= NUSERPARAMS) {
            ASYN_ERROR("%s: Ran out of param slots\n", driverName);
            return asynError;
        }

        switch (drvInfo[0]) {
            case INTEGER_PAR_LETTER:
                createParam(drvInfo, asynParamInt32, &userParams[nextParam++]);
                break;
            case DOUBLE_PAR_LETTER:
                createParam(drvInfo, asynParamFloat64, &userParams[nextParam++]);
                break;
            case STRING_PAR_LETTER:
                createParam(drvInfo, asynParamOctet, &userParams[nextParam++]);
                break;
        }
    }

    return NDPluginDriver::drvUserCreate(pasynUser, drvInfo, pptypeName, psize);
}

/** Callback function that is called by the NDArray driver with new NDArray data.
  * It notifies an available worker to start processing the frame.
  * \param[in] pArray  The NDArray from the callback.
  *
  * Called with this->lock taken
  */
void ADExternalPlugin::processCallbacks(NDArray *pArray)
{
    NDPluginDriver::beginProcessCallbacks(pArray);
    this->unlock();
    _send_frame(pArray);
    this->lock();
}


/** Called when asyn clients call pasynInt32->write().
  * If the parameter is used by the workers, it notifies all the workers about
  * the new value.
  * \param[in] pasynUser pasynUser structure that encodes the reason and address.
  * \param[in] value Value to write.
  *
  * Called with this->lock taken
  */
asynStatus ADExternalPlugin::writeInt32(asynUser *pasynUser, epicsInt32 value) {
    int status = asynSuccess;
    int param = pasynUser->reason;

    status |= NDPluginDriver::writeInt32(pasynUser, value);
    if (nextParam && param >= userParams[0]) {
        const char *paramName;
        getParamName(param, &paramName);
        _send_var_update(paramName, value);
    }

    return (asynStatus) status;
}

/** Called when asyn clients call pasynFloat64->write().
  * If the parameter is used by the workers, it notifies all the workers about
  * the new value.
  * \param[in] pasynUser pasynUser structure that encodes the reason and address.
  * \param[in] value Value to write.
  *
  * Called with this->lock taken
  */
asynStatus ADExternalPlugin::writeFloat64(
    asynUser *pasynUser, epicsFloat64 value)
{
    int status = asynSuccess;
    int param = pasynUser->reason;

    status |= NDPluginDriver::writeFloat64(pasynUser, value);

    if (this->nextParam && param >= userParams[0]) {
        const char *paramName;
        getParamName(param, &paramName);
        _send_var_update(paramName, value);
    }

    return (asynStatus) status;
}

/** Called when asyn clients call pasynOctet->write().
  * If the parameter is used by the workers, it notifies all the workers about
  * the new value.
  * \param[in] pasynUser pasynUser structure that encodes the reason and address.
  * \param[in] value Address of the string to write.
  * \param[in] maxChars Max number of characters to write.
  * \param[out] nActual Number of characters actually written.
  *
  * Called with this->lock taken
  */
asynStatus ADExternalPlugin::writeOctet(asynUser *pasynUser, const char *value,
    size_t maxChars, size_t *nActual)
{
    int status = asynSuccess;
    int param = pasynUser->reason;

    status |= NDPluginDriver::writeOctet(pasynUser, value, maxChars, nActual);

    if (this->nextParam && param >= userParams[0]) {
        const char *paramName;
        getParamName(param, &paramName);
        _send_var_update(paramName, value);
    }

    return (asynStatus) status;
}


void ADExternalPlugin::_broadcast_workers(const char *data, size_t nbytes)
{
    epicsMutexLock(workersMutex);
    for (struct worker_context *worker : this->workers) {
        if (worker->state == WORKER_WORKING) {
            ssize_t rc;
            if((rc=write(worker->sock, data, nbytes)) < 0)
                ASYN_ERROR("%s: unix socket write error %ld\n",
                    driverName, rc);
        }
    }
    epicsMutexUnlock(workersMutex);
}
