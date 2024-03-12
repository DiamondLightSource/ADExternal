import os

from iocbuilder import AutoSubstitution, IocDataStream
from iocbuilder.arginfo import makeArgInfo, Simple, Choice, Ident
from iocbuilder.modules.ADCore import \
    ADCore, includesTemplates, NDPluginBaseTemplate
from iocbuilder.modules.asyn import AsynPort

etc_dir = os.path.dirname(__file__)
top_dir = os.path.dirname(etc_dir)

# worker type choices
WORKER_TYPES = ['Template', 'Gaussian2DFitter', 'MedianFilter', 'AutoExposure']
START_WORKER_SCRIPT = """#!/usr/bin/env bash
{worker_path} {socket_path}
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

    def __init__(self, PORT, P, R, CLASS_NAME, NDARRAY_PORT, NDARRAY_ADDR=0,
                 SOCKET_PATH="/tmp/ext1.sock", SHM_NAME="", QUEUE=5,
                 BLOCK=1, MEMORY=0, PRIORITY=0, STACKSIZE=0, TIMEOUT=1, **args):

        sock_name = os.path.splitext(os.path.basename(SOCKET_PATH))[0]
        if SHM_NAME == "":
            SHM_NAME = "shm_{}".format(sock_name)

        self.__super.__init__(PORT)
        self.__dict__.update(locals())
        self.startWorkerScript = IocDataStream(
            'worker_{}_{}.sh'.format(CLASS_NAME, sock_name), 0555)
        worker_path = "{}/worker/python/{}.py".format(top_dir, CLASS_NAME)
        self.startWorkerScript.write(START_WORKER_SCRIPT.format(
            worker_path=worker_path, socket_path=SOCKET_PATH))
        self.tryCreatingStartAllWorkersScript()
        _ADExternalTemplate(
            PORT=PORT, ADDR=0, P=P, R=R, NDARRAY_PORT=NDARRAY_PORT,
            NDARRAY_ADDR=NDARRAY_ADDR, TIMEOUT=TIMEOUT)

    def tryCreatingStartAllWorkersScript(self):
        # If the file was already there, we ignore the assertion error
        try:
            self.startAllWorkersScript = IocDataStream('workers.sh', 0555)
            self.startAllWorkersScript.write(START_ALL_WORKERS_SCRIPT)
        except:
            pass

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
        CLASS_NAME = Choice("Name of external plugin type", WORKER_TYPES),
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
