#include <stdio.h>
#include <limits.h>
#include <unistd.h>

#include <epicsTime.h>
#include <epicsExit.h>
#include <epicsEvent.h>

#include "ADExternalPlugin.h"

// Used in error printing
static const char *driverName = "ADExternalPlugin";


void ADExternalPlugin::_process_handshake_worker_message(
    struct worker_context *worker, rapidjson::Document &data)
{
    rapidjson::Value::ConstMemberIterator it = data.FindMember("class_name");
    if (it == data.MemberEnd() || !it->value.IsString() || it->value.GetString() != this->className) {
        _send_handshake_not_ok(worker, "class_name not expected");
        server_connection_close(worker->con);
        return;
    }
    _send_handshake_ok(worker);
    epicsMutexLock(workersMutex);
    worker->state = WORKER_WORKING;
    workers.insert(worker);
    epicsMutexUnlock(workersMutex);
    this->lock();
    setIntegerParam(workersNumParam, workers.size());
    callParamCallbacks();
    this->unlock();
    epicsEventSignal(hasWorker);
}


void ADExternalPlugin::_send_handshake_ok(struct worker_context *worker)
{
    rapidjson::StringBuffer string_buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(string_buffer);
    writer.StartObject();
    writer.String("ok");
    writer.Bool(true);
    writer.String("shm_name");
    writer.String(shmName.c_str());
    writer.EndObject();
    epicsMutexLock(workersMutex);
    ssize_t rc;
    if((rc=write(worker->sock,
             string_buffer.GetString(),
             string_buffer.GetSize())) < 0) {
        ASYN_ERROR("%s: unix socket write error %ld\n", driverName, rc);
    }
    epicsMutexUnlock(workersMutex);
}


void ADExternalPlugin::_send_handshake_not_ok(
    struct worker_context *worker, const char *msg)
{
    rapidjson::StringBuffer string_buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(string_buffer);
    writer.StartObject();
    writer.String("ok");
    writer.Bool(false);
    writer.String("err");
    writer.String(msg);
    writer.EndObject();
    epicsMutexLock(workersMutex);
    ssize_t rc;
    if((rc=write(worker->sock,
             string_buffer.GetString(),
             string_buffer.GetSize())) < 0) {
        ASYN_ERROR("%s: unix socket write error %ld\n", driverName, rc);
    }
    epicsMutexUnlock(workersMutex);
}
