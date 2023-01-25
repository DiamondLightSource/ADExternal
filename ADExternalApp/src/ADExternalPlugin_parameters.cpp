#include <stdio.h>
#include <limits.h>
#include <unistd.h>

#include <epicsTime.h>
#include <epicsExit.h>

#include "ADExternalPlugin.h"

// Used in error printing
static const char *driverName = "ADExternalPlugin";


void ADExternalPlugin::_send_var_update(const char *name, epicsInt32 value)
{
    rapidjson::StringBuffer string_buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(string_buffer);
    writer.StartObject();
    writer.String("vars");
    writer.StartObject();
    writer.String(name);
    writer.Int(value);
    writer.EndObject();
    writer.EndObject();
    _broadcast_workers(string_buffer.GetString(), string_buffer.GetSize());
}


void ADExternalPlugin::_send_var_update(const char *name, epicsFloat64 value)
{
    rapidjson::StringBuffer string_buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(string_buffer);
    writer.StartObject();
    writer.String("vars");
    writer.StartObject();
    writer.String(name);
    writer.Double(value);
    writer.EndObject();
    writer.EndObject();
    _broadcast_workers(string_buffer.GetString(), string_buffer.GetSize());
}


// this assumes that it's text
void ADExternalPlugin::_send_var_update(const char *name, const char *value)
{
    rapidjson::StringBuffer string_buffer;
    rapidjson::Writer<rapidjson::StringBuffer> writer(string_buffer);
    writer.StartObject();
    writer.String("vars");
    writer.StartObject();
    writer.String(name);
    writer.String(value);
    writer.EndObject();
    writer.EndObject();
    _broadcast_workers(string_buffer.GetString(), string_buffer.GetSize());
}


void ADExternalPlugin::_update_parameters(rapidjson::Value &ob)
{
    this->lock();
    for (auto &m : ob.GetObject()) {
        if (!m.name.IsString())
            continue;

        int param;
        if(findParam(m.name.GetString(), &param) != asynSuccess) {
            ASYN_ERROR("%s: unable to find param %s\n",
                driverName, m.name.GetString());
            continue;
        }
        if (m.value.IsInt()) {
            setIntegerParam(param, m.value.GetInt());
        } else if (m.value.IsDouble()) {
            setDoubleParam(param, m.value.GetDouble());
        } else if (m.value.IsString()) {
            setStringParam(param, m.value.GetString());
        }
    }
    callParamCallbacks();
    this->unlock();
}


void ADExternalPlugin::_populate_vars_in_json(
    rapidjson::Writer<rapidjson::StringBuffer> &writer)
{
    writer.String("vars");
    writer.StartObject();
    for (int i=0; i < nextParam; i++) {
        int param = userParams[i];
        const char *paramName;
        getParamName(param, &paramName);
        switch (paramName[0]) {
            case INTEGER_PAR_LETTER:
                writer.String(paramName);
                int iparam_val;
                getIntegerParam(param, &iparam_val);
                writer.Int(iparam_val);
                break;
            case DOUBLE_PAR_LETTER:
                writer.String(paramName);
                double dparam_val;
                getDoubleParam(param, &dparam_val);
                writer.Double(dparam_val);
                break;
            case STRING_PAR_LETTER:
                writer.String(paramName);
                std::string sparam_val;
                getStringParam(param, sparam_val);
                writer.String(sparam_val.c_str());
                break;
        }
    }
    writer.EndObject();
}
