#include <stdio.h>
#include <limits.h>
#include <unistd.h>

#include <iocsh.h>
#include <epicsExport.h>

#include "ADExternalPlugin.h"


/** Configuration routine.  Called directly, or from the iocsh function in NDFileEpics */
static int ADExternalPluginConfig( const char *portNameArg, const char *socketPath,
        const char *shmName, const char *className, int queueSize,
        int blockingCallbacks, const char *NDArrayPort, int NDArrayAddr,
        size_t maxMemory, int priority, int stackSize)
{
    // Stack Size must be a minimum of 2MB
    if (stackSize < 2097152)
        stackSize = 2097152;

    // 64MB minimum frame data memory
    if (maxMemory <= 67108864)
        maxMemory = 67108864;

    ADExternalPlugin* adp;
    adp = new ADExternalPlugin(
        portNameArg, socketPath, shmName, className, queueSize,
        blockingCallbacks, NDArrayPort, NDArrayAddr, maxMemory,
        priority, stackSize);
    adp->start();
    return asynSuccess;
}

/* EPICS iocsh shell commands */
static const iocshArg initArg0 = {"portName", iocshArgString};
static const iocshArg initArg1 = {"socketPath", iocshArgString};
static const iocshArg initArg2 = {"shmName", iocshArgString};
static const iocshArg initArg3 = {"className", iocshArgString};
static const iocshArg initArg4 = {"queueSize", iocshArgInt};
static const iocshArg initArg5 = {"blockingCallbacks", iocshArgInt};
static const iocshArg initArg6 = {"NDArrayPort", iocshArgString};
static const iocshArg initArg7 = {"NDArrayAddr", iocshArgInt};
static const iocshArg initArg8 = {"maxMemory", iocshArgInt};
static const iocshArg initArg9 = {"priority", iocshArgInt};
static const iocshArg initArg10 = {"stackSize", iocshArgInt};
static const iocshArg *const initArgs[] = {&initArg0,
                                           &initArg1,
                                           &initArg2,
                                           &initArg3,
                                           &initArg4,
                                           &initArg5,
                                           &initArg6,
                                           &initArg7,
                                           &initArg8,
                                           &initArg9,
                                           &initArg10};


static const iocshFuncDef initFuncDef = {
    "ADExternalConfig", 11, initArgs, // "Initialise ADExternal plugin"
};


static void initCallFunc(const iocshArgBuf *args)
{
    ADExternalPluginConfig(
        args[0].sval, args[1].sval, args[2].sval, args[3].sval, args[4].ival,
        args[5].ival, args[6].sval, args[7].ival, args[8].ival, args[9].ival,
        args[10].ival);
}


static void ADExternalPluginRegister(void)
{
    iocshRegister(&initFuncDef,initCallFunc);
}


extern "C" {
    epicsExportRegistrar(ADExternalPluginRegister);
}
