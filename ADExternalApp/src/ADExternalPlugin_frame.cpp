#include <stdio.h>
#include <limits.h>
#include <unistd.h>

#include <epicsTime.h>
#include <epicsExit.h>
#include <epicsEvent.h>

#include "utils.h"

#include "ADExternalPlugin.h"

// Used in error printing
static const char *driverName = "ADExternalPlugin";


bool ADExternalPlugin::_send_frame_to_worker(
    struct worker_context *worker, NDArray *pArray)
{
    epicsTimeGetCurrent(&worker->ts_start);
    rapidjson::StringBuffer string_buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(string_buffer);
    writer.StartObject();
    writer.String("frame_dims");
    writer.StartArray();
    for (int i=0; i < pArray->ndims; i++) {
        writer.Int((int) pArray->dims[i].size);
    }
    writer.EndArray();
    writer.String("data_type");
    writer.String(ad_data_type_to_string(pArray->dataType));
    writer.String("frame_id");
    writer.Int(pArray->uniqueId);
    writer.String("frame_loc");
    writer.Uint64((uint64_t) pArray->pData - (uint64_t) shmem->addr);
    writer.EndObject();
    ssize_t rc;
    if((rc=write(worker->sock,
             string_buffer.GetString(),
             string_buffer.GetSize())) < 0) {
        ASYN_ERROR("%s: unix socket write error %ld\n", driverName, rc);
        return false;
    }
    return true;
}


bool ADExternalPlugin::_send_frame(NDArray *pArray)
{
    if (!shared_mem_is_included(shmem, pArray->pData)) {
        ASYN_ERROR("%s: frame data not in shared memory\n", driverName);
        return false;
    }
    bool got_worker = false;
    for (;;) {
        epicsMutexLock(workersMutex);
        for (struct worker_context *worker : this->workers) {
            if (!worker->frame) {
                pArray->reserve();
                worker->frame = pArray;
                _send_frame_to_worker(worker, pArray);
                got_worker = true;
                break;
            }
        }
        epicsMutexUnlock(workersMutex);
        if (got_worker)
            break;
        epicsEventWait(hasWorker);
    }
    return got_worker;
}


void ADExternalPlugin::_populate_attrs_in_json(
    rapidjson::Writer<rapidjson::StringBuffer> &writer, NDArray *pArray)
{
    writer.String("attrs");
    writer.StartObject();
    // TODO: to be implemented
    writer.EndObject();
}


void ADExternalPlugin::_populate_attrs_in_frame(
    rapidjson::Value &attrs, NDArray *pArray)
{
    for (rapidjson::Value::ConstMemberIterator it=attrs.MemberBegin();
         it != attrs.MemberEnd();
         it++) {
        const char *name = it->name.GetString();
        if (it->value.IsInt()) {
            int ival = it->value.GetInt();
            pArray->pAttributeList->add(name, name, NDAttrInt32, &ival);
        } else if (it->value.IsDouble()) {
            int dval = it->value.GetDouble();
            pArray->pAttributeList->add(name, name, NDAttrFloat64, &dval);
        } else if (it->value.IsString()) {
            const char *sval = it->value.GetString();
            // TODO: check that sval is copied
            pArray->pAttributeList->add(
                name, name, NDAttrString, (char *) sval);
        }
    }
}
