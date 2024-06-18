import os

from iocbuilder import AutoSubstitution, IocDataStream, iocinit
from iocbuilder.arginfo import makeArgInfo, Simple, Choice, Ident
from iocbuilder.modules.ADCore import \
    ADCore, includesTemplates, NDPluginBaseTemplate
from iocbuilder.modules.asyn import AsynPort

etc_dir = os.path.dirname(__file__)
top_dir = os.path.dirname(etc_dir)

# worker type choices
WORKER_TYPES = ['Template', 'Gaussian2DFitter', 'MedianFilter', 'AutoExposure']
START_WORKER_SCRIPT = """#!/usr/bin/env bash
{python} {worker_path} {socket_path}
"""
START_ZMQWORKER_SCRIPT = """#!/usr/bin/env bash
{python} {worker_path} {options} {socket_path} {class_name} {endpoint}
"""
START_ALL_WORKERS_SCRIPT = """#!/usr/bin/env bash
DIR=$(dirname "$0")
run_forever() {
    echo "Starting $*"
    while true; do
        $@
        echo "task $* died, restarting in a few seconds..."
        sleep 8
    done
}
trap "kill 0" EXIT
pids=()
for worker in $DIR/worker_*.sh; do
    ( run_forever "$worker"; ) &
    pids+=($!)
done
while true; do
    wait || break
done
"""


@includesTemplates(NDPluginBaseTemplate)
class _ADExternalTemplate(AutoSubstitution):
    TemplateFile = 'ADExternal.template'


class TemplateTemplate(AutoSubstitution):
    TemplateFile = 'ADExternalTemplate.template'


class Gaussian2DFitterTemplate(AutoSubstitution):
    TemplateFile = 'ADExternalGaussian2DFitter.template'


class MedianFilterTemplate(AutoSubstitution):
    TemplateFile = 'ADExternalMedianFilter.template'


class AutoExposureTemplate(AutoSubstitution):
    TemplateFile = 'ADExternalAutoExposure.template'


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

    def __init__(self, PORT, P, R, CLASS_NAME, NDARRAY_PORT,
                 NDARRAY_ADDR=0, IDENTITY="", SOCKET_PATH="/tmp/ext1.sock",
                 SHM_NAME="", PYTHON="", QUEUE=5, BLOCK=1, MEMORY=0, PRIORITY=0,
                 STACKSIZE=0, TIMEOUT=1, **args):
        self.__super.__init__(PORT)
        self.__dict__.update(locals())
        self.createWorkerScript()
        self.tryCreatingStartAllWorkersScript()
        _ADExternalTemplate(
            PORT=PORT, ADDR=0, P=P, R=R, NDARRAY_PORT=NDARRAY_PORT,
            NDARRAY_ADDR=NDARRAY_ADDR, TIMEOUT=TIMEOUT)

    def createWorkerScript(self):
        sock_name = os.path.splitext(os.path.basename(self.SOCKET_PATH))[0]
        self.startWorkerScript = IocDataStream(
            'worker_{}_{}.sh'.format(self.CLASS_NAME, sock_name), 0555)
        worker_path = "{}/worker/python/{}.py".format(top_dir, self.CLASS_NAME)
        self.startWorkerScript.write(START_WORKER_SCRIPT.format(
            python=self.PYTHON, worker_path=worker_path,
            socket_path=self.SOCKET_PATH))

    def tryCreatingStartAllWorkersScript(self):
        # If the file was already there, we ignore the assertion error
        try:
            self.startAllWorkersScript = IocDataStream('workers.sh', 0555)
            self.startAllWorkersScript.write(START_ALL_WORKERS_SCRIPT)
        except:
            pass

    def InitialiseOnce(self):
        print("# ADExternalConfig(portName, socketPath, shmName, className, "
              "identity, queueSize, blockingCallbacks, NDArrayPort, "
              "NDArrayAddr, maxMemory, priority, stackSize)")

    def Initialise(self):
        # we can't do this in the constructor because ioc_name was not # at that time
        if self.SHM_NAME == "":
            self.SHM_NAME = "shm_{}".format(iocinit.iocInit().ioc_name)

        print(
            "ADExternalConfig(\"{PORT}\", \"{SOCKET_PATH}\", \"{SHM_NAME}\", "
             "\"{CLASS_NAME}\", \"{IDENTITY}\", {QUEUE}, {BLOCK}, "
             "\"{NDARRAY_PORT}\", " "{NDARRAY_ADDR}, {MEMORY}, {PRIORITY}, "
             "{STACKSIZE})".format(**self.__dict__))

    ArgInfo = makeArgInfo(__init__,
        PORT = Simple("Port name", str),
        P = Simple("PV prefix 1", str),
        R = Simple("PV prefix 2", str),
        CLASS_NAME = Choice("Name of external plugin type", WORKER_TYPES),
        IDENTITY = Simple("Source identity", str),
        NDARRAY_PORT = Ident('Input array port', AsynPort),
        NDARRAY_ADDR = Simple('Input array port address', int),
        SOCKET_PATH = Simple("Path to unix socket", str),
        SHM_NAME = Simple("Shared memory name", str),
        PYTHON = Simple("Path to python used to run the workers", str),
        QUEUE = Simple('Input array queue size', int),
        BLOCK = Simple('Blocking callbacks?', int),
        MEMORY = Simple("Memory", int),
        PRIORITY = Simple("Priority", int),
        STACKSIZE = Simple("Stack size", int),
        TIMEOUT = Simple("Timeout", int)
        )


# This is similar to ADExternal but it will create a worker startup
# startWorkerScript which start the worker using the ZMQ forwarder
class ADExternalZmqForwarder(ADExternal):
    def __init__(self, PORT, P, R, ENDPOINT, CLASS_NAME, NDARRAY_PORT,
                 SEND_DATA=False, NDARRAY_ADDR=0, IDENTITY="",
                 SOCKET_PATH="/tmp/ext1.sock", SHM_NAME="", PYTHON="", QUEUE=5,
                 BLOCK=1, MEMORY=0, PRIORITY=0, STACKSIZE=0, TIMEOUT=1, **args):
        self.ENDPOINT = ENDPOINT
        self.SEND_DATA = SEND_DATA
        ADExternal.__init__(self, PORT, P, R, CLASS_NAME,
                            NDARRAY_PORT, NDARRAY_ADDR, IDENTITY, SOCKET_PATH,
                            SHM_NAME, PYTHON, QUEUE, BLOCK, MEMORY, PRIORITY,
                            STACKSIZE, TIMEOUT, **args)


    def createWorkerScript(self):
        sock_name = os.path.splitext(os.path.basename(self.SOCKET_PATH))[0]
        self.startWorkerScript = IocDataStream(
            'worker_{}_{}.sh'.format(self.CLASS_NAME, sock_name), 0555)
        worker_path = '{}/worker/python/ZmqForwarder.py'.format(top_dir)
        options = '' if not self.SEND_DATA else '--with_frame_data'
        self.startWorkerScript.write(START_ZMQWORKER_SCRIPT.format(
            python=self.PYTHON, worker_path=worker_path,
            socket_path=self.SOCKET_PATH, class_name=self.CLASS_NAME,
            endpoint=self.ENDPOINT, options=options))

    ArgInfo = makeArgInfo(__init__,
        PORT = Simple("Port name", str),
        P = Simple("PV prefix 1", str),
        R = Simple("PV prefix 2", str),
        ENDPOINT = Simple('ZMQ endpoint', str),
        SEND_DATA = Simple('Whether to send frame data too', bool),
        CLASS_NAME = Choice("Name of external plugin type", WORKER_TYPES),
        IDENTITY = Simple("Source identity", str),
        NDARRAY_PORT = Ident('Input array port', AsynPort),
        NDARRAY_ADDR = Simple('Input array port address', int),
        SOCKET_PATH = Simple("Path to unix socket", str),
        SHM_NAME = Simple("Shared memory name", str),
        PYTHON = Simple("Path to python used to run the workers", str),
        QUEUE = Simple('Input array queue size', int),
        BLOCK = Simple('Blocking callbacks?', int),
        MEMORY = Simple("Memory", int),
        PRIORITY = Simple("Priority", int),
        STACKSIZE = Simple("Stack size", int),
        TIMEOUT = Simple("Timeout", int)
        )
