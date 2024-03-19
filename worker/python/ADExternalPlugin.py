import ctypes
import json
import logging
import mmap
import numpy
import os
import socket

try:
    from math import prod
except ImportError:
    def prod(iterable):
        res = 1
        for item in iterable:
            res *= item

        return res


MAX_RECV_LEN = 4096
PARAMS_FIELD = 'vars'
ATTRS_FIELD = 'attrs'


class ADExternalPlugin(object):
    # init our param dict
    def __init__(self, socket_path, initial_params=None):
        self.log = logging.getLogger(self.__class__.__name__)
        self.socket_path = socket_path
        self._params = {} if initial_params is None else dict(initial_params)
        self._new_params = {}
        self.post_process_hook = None

    def set_post_process_hook(self, func):
        self.post_process_hook = func

    # get a param value
    def __getitem__(self, param):
        return self._params[param]

    # set a param value
    def __setitem__(self, param, value):
        assert param in self, 'Param %s not in param lib' % param
        self._params[param] = value
        self._new_params[param] = value

    def update_params(self, params):
        for key, val in params.items():
            self[key] = val

    # see if param is supported
    def __contains__(self, param):
        return param in self._params

    # length of param dict
    def __len__(self):
        return len(self._params)

    # for if we want to print the dict
    def __repr__(self):
        return repr(self._params)

    # iter
    def __iter__(self):
        return iter(self._params)

    # default paramChanged does nothing
    def params_changed(self, params):
        pass

    def process_array(self, arr, attrs):
        return arr

    def on_connected(self, server_params={}):
        pass

    def pop_new_params(self):
        new_params = self._new_params
        self._new_params = {}
        return new_params

    def _send_msg(self, msg):
        self.log.debug('Sending message: %s', msg)
        data = json.dumps(msg).encode()
        self.sock.send(data)

    def _recv_msg(self):
        data = self.sock.recv(MAX_RECV_LEN)
        self.log.debug('Received raw message: %s', repr(data))
        if data == b'':
            return None

        return json.loads(data)

    def _mmap_shared_memory(self, shm_name):
        self.shm_name = shm_name
        path = '/dev/shm/%s' % (shm_name,)
        self.shm_size = os.stat(path).st_size
        fd = os.open(path, os.O_RDWR)
        self.mem = mmap.mmap(fd, self.shm_size)
        self.mem_view = numpy.frombuffer(self.mem, 'uint8')

    def connect(self, socket_path):
        if self.sock:
            self.sock.close()

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET, 0)
        self.sock.connect(socket_path)
        self.socket_path = socket_path

    def _update_from_recved_params(self, params):
        if params:
            self._params.update(params)
            self.params_changed(params)

    def _is_offset_inside_shmem(self, offset):
        return offset >= 0 and offset < self.shm_size

    @staticmethod
    def _convert_dims(dims):
        # dimensions in numpy arrays are interpreted reversed to dimensions
        # in NDArrays
        return tuple(reversed(dims))

    def _get_array_from_shared_memory(self, offset, dims, dtype_name):
        dt = numpy.dtype(dtype_name)
        nelem = prod(dims)
        nbytes = nelem * dt.itemsize
        stop_offset = offset + nbytes
        if not self._is_offset_inside_shmem(offset) or not \
                self._is_offset_inside_shmem(stop_offset - 1):
            raise ValueError(
                'Outside of shared memory Offset=%d dims=%s dtype=%s' %
                (offset,  str(dims), dtype_name))

        return self.mem_view[offset:stop_offset] \
            .view(dtype_name) \
            .reshape(self._convert_dims(dims))

    def run(self):
        self.sock = None
        self.connect(self.socket_path)
        name = getattr(self, 'name', self.__class__.__name__)
        self._send_msg({'class_name': name})
        msg = self._recv_msg()

        if msg is None:
            self.log.error('Connection was closed before handshake completion')
            return

        if not msg.get('ok'):
            self.log.error('Failed during handshake: %s', msg.get('err'))
            return

        server_params = msg.get(PARAMS_FIELD, {})
        self._update_from_recved_params(server_params)
        self._mmap_shared_memory(msg['shm_name'])

        new_params = self.pop_new_params()

        # make sure they receive parameters value forced by us
        self._send_msg({PARAMS_FIELD: new_params})

        self.on_connected(server_params)

        while True:
            in_msg = self._recv_msg()
            if in_msg is None:
                self.log.debug('We were disconnected from server')
                break

            self._update_from_recved_params(in_msg.get(PARAMS_FIELD, {}))
            frame_offset = in_msg.get('frame_loc')
            if frame_offset is not None:
                arr = self._get_array_from_shared_memory(
                    frame_offset, in_msg.get('frame_dims'),
                    in_msg.get('data_type'))
                old_arr_shape = arr.shape
                old_arr_dtype = arr.dtype.name
                old_arr_nbytes = arr.nbytes
                old_arr_data = arr.ctypes.data
                self.log.debug(
                    'Received frame with buffer in %x', old_arr_data)
                attrs = {}

                new_arr = self.process_array(arr, attrs)

                new_params = self.pop_new_params()
                if new_arr is None:
                    # we didn't produce any frame but parameter might have
                    # been updated
                    out_msg = {
                        'push_frame': False,
                        PARAMS_FIELD: new_params
                    }
                else:
                    if new_arr.ctypes.data != old_arr_data:
                        nbytes = min(old_arr_nbytes, new_arr.nbytes)
                        self.log.debug(
                            'Copying array data from %x to %x nbytes=%d',
                            new_arr.ctypes.data, old_arr_data, nbytes)
                        ctypes.memmove(
                            old_arr_data,
                            new_arr.ctypes.data,
                            nbytes
                        )

                    out_msg = {
                        'push_frame': True,
                        PARAMS_FIELD: new_params,
                        ATTRS_FIELD: attrs
                    }
                    if old_arr_shape != new_arr.shape:
                        out_msg['frame_dims'] = \
                            self._convert_dims(new_arr.shape)

                    if old_arr_dtype != new_arr.dtype.name:
                        out_msg['data_type'] = new_arr.dtype.name

                if self.post_process_hook:
                    self.post_process_hook(arr, in_msg, out_msg)

                self._send_msg(out_msg)
