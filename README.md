# ADExternal

ADExternal is an areaDetector plugin to process a frame in an external
process minimising data copying by using shared memory.

The processing side (external process) is called `worker`, examples of it
can be found under folder `worker/python`.

A worker can be implemented in any language, the protocol is documented in
 [PROTOCOL](PROTOCOL.md)

## Features
- The EPICS side is assolated of the processing side and therefore a failure
in the processing task will not affect EPICS stability
- Frame is passed to the worker using shared memory, therefore, minimising
overhead
- A worker can add attributes to the frame
- A worker can update PV values
- A worker can process a frame in place or might prefer to create a new frame
- There can be more than one worker to process in parallel

## Limitations
- This plugin makes ADCore use shared memory for frame allocation and therefore,
 it requires a version of ADCore that allows doing that.
- There can only be one of this type of plugin
- The asyn parameters that are updated by the worker should have a name that
 starts with a letter indicating the type (`i` for integer, `d` for double or
 `s` for string)

## Quickstart
- Configure the plugin in the target IOC
```c
# ADExternalConfig(
#    portName, socketPath, shmName, className,
#    queueSize, blockingCallbacks, NDArrayPort, NDArrayAddr, maxMemory,
#    priority, stackSize)
ADExternalConfig(
    "ad.ext", "/tmp/unix_sock_name.sock", "shm_name1", "Template",
    5, 1, "ad.cam", 0, 67108864,
    0, 0)
```
In this case, it uses an example worker type called `Template`.

`maxMemory` specifies shared memory size.

- Run the worker passing the path to the unix socket
```bash
$ python worker/python/ADExternalTemplate.py /tmp/unix_sock_name.sock
```
