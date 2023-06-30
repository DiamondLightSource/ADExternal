from iocbuilder import AutoSubstitution, Device
from iocbuilder.arginfo import *
from iocbuilder.modules.ADCore import \
    ADCore, includesTemplates, NDPluginBaseTemplate
from iocbuilder.modules.asyn import AsynPort


@includesTemplates(NDPluginBaseTemplate)
class _ADExternalTemplate(AutoSubstitution):
    TemplateFile = 'ADExternal.template'


# Main device class
class ADExternal(AsynPort):

    # Dependencies
    Dependencies = (ADCore,)

    # Database definitions
    DbdFileList = ['ADExternal']

    # Library
    LibFileList = ['ADExternal']

    # Is an Asyn device
    IsAsyn = True

    # worker type choices
    worker_type = ['Template', 'Gaussian2DFitter']

    def __init__(self, PORT, P, R, CLASS_NAME, NDARRAY_PORT, NDARRAY_ADDR=0,
                 SOCKET_PATH="/tmp/ext1.sock", SHM_NAME="shm1", QUEUE=5,
                 BLOCK=1, MEMORY=0, PRIORITY=0, STACKSIZE=0, TIMEOUT=1, **args):
        self.__super.__init__(PORT)
        self.__dict__.update(locals())

        # The template wants the asyn port of this driver
        _ADExternalTemplate(
            PORT=PORT, ADDR=0, P=P, R=R, NDARRAY_PORT=NDARRAY_PORT,
            NDARRAY_ADDR=NDARRAY_ADDR, TIMEOUT=TIMEOUT)

        class _tmp(AutoSubstitution):
            TemplateFile = 'ADExternal%s.template' % (CLASS_NAME,)
            TrueName = '_ADExternal%s' % (CLASS_NAME,)
            ModuleName = ADExternal.ModuleName

        _tmp(PORT=PORT, ADDR=0, P=P, R=R, TIMEOUT=TIMEOUT)

    def InitialiseOnce(self):
        print("# ADExternalConfig(portName, socketPath, shmName, className, "
              "queueSize, blockingCallbacks, NDArrayPort, NDArrayAddr, "
              "maxMemory, priority, stackSize)")

    def Initialise(self):
        print(
            "ADExternalConfig(\"{PORT}\", \"{SOCKET_PATH}\", \"{SHM_NAME}\", "
             "\"{CLASS_NAME}\", {QUEUE}, {BLOCK}, \"{NDARRAY_PORT}\", "
            "{NDARRAY_ADDR}, {MEMORY}, {PRIORITY}, {STACKSIZE})".format(
                **self.__dict__))

    ArgInfo = makeArgInfo(__init__,
        PORT = Simple("Port name", str),
        P = Simple("PV prefix 1", str),
        R = Simple("PV prefix 2", str),
        CLASS_NAME = Choice("Name of external plugin type", worker_type),
        NDARRAY_PORT = Ident('Input array port', AsynPort),
        NDARRAY_ADDR = Simple('Input array port address', int),
        SOCKET_PATH = Simple("Path to unix socket", str),
        SHM_NAME = Simple("Shared memory name", str),
        QUEUE = Simple('Input array queue size', int),
        BLOCK = Simple('Blocking callbacks?', int),
        MEMORY = Simple("Memory", int),
        PRIORITY = Simple("Priority", int),
        STACKSIZE = Simple("Stack size", int),
        TIMEOUT = Simple("Timeout", int)
        )
