#include <stdio.h>
#include <limits.h>
#include <unistd.h>

#include <iocsh.h>
#include <epicsExport.h>

#include "ADExternalPlugin.h"


/** Configuration routine.  Called directly, or from the iocsh function in NDFileEpics */
static int ADExternalPluginConfig( const char *portNameArg, const char *socketPath,
        const char *shmName, const char *className, const char *identity,
        int queueSize, int blockingCallbacks, const char *NDArrayPort,
        int NDArrayAddr, size_t maxMemory, int priority, int stackSize)
{
    // Stack Size must be a minimum of 2MB
    if (stackSize < 2097152)
        stackSize = 2097152;

    // 64MB minimum frame data memory
    if (maxMemory <= 67108864)
        maxMemory = 67108864;

    ADExternalPlugin* adp;
    adp = new ADExternalPlugin(
        portNameArg, socketPath, shmName, className, identity, queueSize,
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
static const iocshArg initArg4 = {"identity", iocshArgString};
static const iocshArg initArg5 = {"queueSize", iocshArgInt};
static const iocshArg initArg6 = {"blockingCallbacks", iocshArgInt};
static const iocshArg initArg7 = {"NDArrayPort", iocshArgString};
static const iocshArg initArg8 = {"NDArrayAddr", iocshArgInt};
static const iocshArg initArg9 = {"maxMemory", iocshArgInt};
static const iocshArg initArg10 = {"priority", iocshArgInt};
static const iocshArg initArg11 = {"stackSize", iocshArgInt};
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
                                           &initArg10,
                                           &initArg11};


static const iocshFuncDef initFuncDef = {
    "ADExternalConfig", 12, initArgs, // "Initialise ADExternal plugin"
};


static void initCallFunc(const iocshArgBuf *args)
{
    ADExternalPluginConfig(
        args[0].sval, args[1].sval, args[2].sval, args[3].sval, args[4].sval,
        args[5].ival, args[6].ival, args[7].sval, args[8].ival, args[9].ival,
        args[10].ival, args[11].ival);
}


static void ADExternalPluginRegister(void)
{
    iocshRegister(&initFuncDef, initCallFunc);
}


extern "C" {
    epicsExportRegistrar(ADExternalPluginRegister);
}
