#ifndef _AD_EXTERNAL_PLUGIN_H
#define _AD_EXTERNAL_PLUGIN_H

#include "rapidjson/document.h"
#include "rapidjson/writer.h"
#include "rapidjson/stringbuffer.h"

#include "NDPluginDriver.h"
#include "server.h"
#include "shared_mem.h"

#define INTEGER_PAR_LETTER 'i'
#define DOUBLE_PAR_LETTER 'd'
#define STRING_PAR_LETTER 's'


// Max number of user parameters in a subclass
#define NUSERPARAMS 100

#define ASYN_ERROR(...) asynPrint(pasynUserSelf, ASYN_TRACE_ERROR, __VA_ARGS__)
#define ASYN_WARN(...) asynPrint(pasynUserSelf, ASYN_TRACE_WARNING, __VA_ARGS__)
#define ASYN_FLOW(...) asynPrint(pasynUserSelf, ASYN_TRACE_FLOW, __VA_ARGS__)


enum worker_state {
    WORKER_HANDSHAKE,
    WORKER_WORKING,
};


struct worker_context {
    enum worker_state state;
    struct server_connection *con;
    int sock;
    NDArray *frame;
    epicsTimeStamp ts_start;
};


class ADExternalPlugin : public NDPluginDriver {
public:
    ADExternalPlugin(const char *portName, const char *socketPath,
                     const char *shmName, const char *classname,
                     int queueSize, int blockingCallbacks,
                     const char *NDArrayPort, int NDArrayAddr,
                     size_t maxMemory, int priority, int stackSize);

    ~ADExternalPlugin() {};

    void shutdown();

    void comTask();

    /** This is called when the plugin gets a new array callback */
    virtual void processCallbacks(NDArray *pArray);

    /** This is when we get a new int value */
    virtual asynStatus writeInt32(asynUser *pasynUser, epicsInt32 value);

    /** This is when we get a new float value */
    virtual asynStatus writeFloat64(asynUser *pasynUser, epicsFloat64 value);

    /** This is when we get a new string value */
    virtual asynStatus writeOctet(asynUser *pasynUser, const char *value, size_t maxChars, size_t *nActual);

    virtual asynStatus drvUserCreate(
        asynUser *pasynUser, const char *drvInfo, const char **pptypeName,
        size_t *psize);

protected:
    /** These are the values of our parameters */
    int workersNumParam;
    int classNameParam;
    int procTimeParam;
    int userParams[NUSERPARAMS];

private:
    std::string shmName;

    std::string className;

    size_t max_frame_size;

    struct server_context *server;

    struct shared_mem_context *shmem;

    void _handle_server_events();

    void _initialise_new_connection(struct server_connection *con);

    void _destroy_connection(struct server_connection *con);

    void _process_worker_message(
        struct worker_context *worker, rapidjson::Document &data);

    void _process_handshake_worker_message(
        struct worker_context *worker, rapidjson::Document &data);

    void _process_working_worker_message(
        struct worker_context *worker, rapidjson::Document &data);

    void _populate_vars_in_json(
        rapidjson::Writer<rapidjson::StringBuffer> &writer);

    void _populate_attrs_in_json(
        rapidjson::Writer<rapidjson::StringBuffer> &writer, NDArray *pArray);

    void _populate_attrs_in_frame(
        rapidjson::Value &attrs, NDArray *pArray);

    void _update_parameters(rapidjson::Value &ob);

    void _send_handshake_ok(struct worker_context *worker);

    void _send_handshake_not_ok(struct worker_context *worker, const char *msg);

    void _send_var_update(const char *name, epicsInt32 val);

    void _send_var_update(const char *name, epicsFloat64 val);

    void _send_var_update(const char *name, const char *val);

    void _broadcast_workers(const char *data, size_t nbytes);

    bool _send_frame_to_worker(struct worker_context *worker, NDArray *pArray);

    bool _send_frame(NDArray *pArray);

    asynStatus importAdPythonModule();

    asynStatus makePyInst();

    asynStatus interpretReturn(void *pValue);

    NDAttributeList *pFileAttributes;

    int nextParam;

    epicsMutexId workersMutex;
 
    epicsEventId hasWorker;

    std::set<struct worker_context *> workers;
};

void endProcessingThread(void* plugin);

#endif
