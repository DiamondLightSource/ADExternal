#include <iocsh.h>
#include <epicsExport.h>

#include "shared_mem.h"

extern struct shared_mem_context *_global_shared_mem;


static const iocshFuncDef initFuncDef = {
    "shared_mem_print", 0, NULL
};


static void initCallFunc(const iocshArgBuf *args)
{
    if (_global_shared_mem) {
        shared_mem_print(_global_shared_mem);
    }
}


static void SharedMemCommandRegister(void)
{
    iocshRegister(&initFuncDef, initCallFunc);
}


extern "C" {
    epicsExportRegistrar(SharedMemCommandRegister);
}
