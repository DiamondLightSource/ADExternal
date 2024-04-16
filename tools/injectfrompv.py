#!/usr/bin/env python
import atexit
import argparse
import cothread
import ctypes
import json
import logging
import mmap
import numpy
import os
import socket
import threading

from collections import deque
from cothread import catools, cosocket

log = logging.getLogger(__name__)

# WARNING: this is a test script and should not be used in production


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data_pv', required=True)
    parser.add_argument('--socket-path', required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--data-type', default='uint8')
    parser.add_argument('--loglevel', default='INFO')
    parser.add_argument('--shm-name', default='shm_injectfrompv')
    parser.add_argument('--shm-size', type=int, default=64*1024*1024)
    return parser.parse_args()


class SharedMem(object):
    def __init__(self, shm_name, size):
        self.log = logging.getLogger(self.__class__.__name__)
        self.filepath = f'/dev/shm/{shm_name}'
        self.size = size
        self.fd = os.open(self.filepath, os.O_RDWR | os.O_CREAT)
        assert self.fd >= 0
        atexit.register(self.destroy)
        os.ftruncate(self.fd, self.size)
        self.mem = mmap.mmap(self.fd, self.size)
        self.mem_view = numpy.frombuffer(self.mem, 'uint8')
        self.free_all()

    def alloc(self, size):
        for i, (off, sz) in enumerate(self.free_list):
            if sz >= size:
                self.free_list[i] = (off + size, sz - size)
                self.log.info('allocating %d bytes at offset %d',
                              size, off)
                self.occupied_size[off] = size
                return off

        return None

    def get_view(self, off):
        return self.mem_view[off:off + self.occupied_size[off]]

    def free(self, off):
        self.log.info('Freeing %d bytes at %d', self.occupied_size[off], off)
        size = self.occupied_size.pop(off)
        self.free_list.append((off, size))

    def free_all(self):
        self.log.info('Freeing all memory')
        self.free_list = [(0, self.size)]
        self.occupied_size = {}

    def destroy(self):
        os.close(self.fd)
        os.unlink(self.filepath)
        atexit.unregister(self.destroy)


class SocketServer(object):
    def __init__(self,
                 socket_path,
                 on_client_connected=None,
                 on_client_disconnected=None,
                 asynchronous=False):
        self.asynchronous = asynchronous
        if self.asynchronous:
            cothread.socket_hook()

        self.socket_path = socket_path
        self.client = None
        self.log = logging.getLogger(self.__class__.__name__)
        self.on_client_connected = on_client_connected
        self.on_client_disconnected = on_client_disconnected
        self.request_quit = False

    def bind_socket(self):
        if self.asynchronous:
            self.sock = cosocket.cosocket(
                socket.AF_UNIX, socket.SOCK_SEQPACKET, 0)
        else:
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET, 0)
                
        self.sock.settimeout(0.1)
        self.sock.bind(self.socket_path)
        self.sock.listen(1)

    def destroy(self):
        self.request_quit = True
        atexit.unregister(self.destroy)

    def run(self):
        while not self.request_quit:
            try:
                client, addr = self.sock.accept()
            except (socket.timeout, TimeoutError):
                # provide an oportunity to exit the loop
                continue
            except KeyboardInterrupt:
                break

            self.log.info(f'Accepted connection from {addr}')
            if self.client:
                log.warning('Closing previous connection')
                self.destroy_client()

            self.client = client
            if self.on_client_connected:
                self.on_client_connected(self)

        self.destroy_listening_socket()

    def destroy_client(self):
        if self.client:
            self.client.close()
            if self.on_client_disconnected:
                self.on_client_disconnected(self)

            self.client = None

    def destroy_listening_socket(self):
        self.sock.close()
        os.unlink(self.socket_path)

    def send_json(self, data):
        if self.client is None:
            self.log.debug('No client connected when trying to send data')
            return

        try:
            self.client.send(json.dumps(data).encode('utf-8'))
        except (BrokenPipeError, ConnectionResetError):
            self.log.error('Failed to send data')
        
    def recv_json(self):
        if self.client is None:
            self.log.debug('No client connected when trying to receive data')
            return

        client_disconnected = False
        data = b''
        try:
            data = self.client.recv(4096)
            client_disconnected = data == b''
        except (BrokenPipeError, ConnectionResetError):
            client_disconnected = True
        except TimeoutError:
            return None

        if client_disconnected:
            log.info('Client disconnected')
            self.destroy_client()
            return None

        try:
            return json.loads(data)
        except json.JSONDecodeError:
            log.error('Failed to decode JSON data: %s', data)
            return None

    def start(self):
        self.bind_socket()
        if self.asynchronous:
            cothread.Spawn(self.run)
        else:
            threading.Thread(target=self.run).start()

        atexit.register(self.destroy)


class PVListener(object):
    def __init__(self, pv_name, new_data_hook=None):
        self.pv_name = pv_name
        self.new_data_hook = new_data_hook
        self.log = logging.getLogger(self.__class__.__name__)

    def start(self):
        catools.camonitor(
            self.pv_name, self.new_data, format=catools.FORMAT_TIME)

    def new_data(self, pv):
        if self.new_data_hook:
            self.new_data_hook(pv)


def main():
    args = parse_args()
    logging.basicConfig(level=args.loglevel)
    frame_nbytes = args.width * args.height * numpy.dtype(args.data_type).itemsize
    shm_offsets = deque()
    shm = SharedMem(args.shm_name, args.shm_size)

    def on_client_connected(server):
        handshake = server.recv_json()
        log.info('handshake: %s', handshake)
        server.send_json({'ok': True, 'shm_name': args.shm_name, 'vars': {}})

    def on_client_disconnected(server):
        shm.free_all()

    socket_server = SocketServer(
        args.socket_path, on_client_connected, on_client_disconnected, True)
    socket_server.start()

    def new_data_hook(pv):
        log.info('new data from PV: %s', pv.name)
        if socket_server.client is None:
            log.warning('No client connected')
            return

        mem_off = shm.alloc(frame_nbytes)
        shm_offsets.append(mem_off)
        if mem_off is None:
            log.error('Failed to allocate shared memory')
            return
        
        frame_data = +pv
        ctypes.memmove(shm.get_view(mem_off).ctypes.data,
                      frame_data.ctypes.data,
                      frame_nbytes)
        frame_info = {
            'frame_dims': (args.width, args.height),
            'data_type': args.data_type,
            'frame_loc': mem_off,
            'ts': pv.timestamp
        }
        log.info('Sending frame info: %s', frame_info)
        socket_server.send_json(frame_info)

    def frame_releaser():
        while True:
            msg = socket_server.recv_json()
            if msg is None:
                cothread.Yield()
                continue

            log.info('Received message: %s', msg)
            if 'push_frame' in msg and shm_offsets:
                shm.free(shm_offsets.popleft())

    cothread.Spawn(frame_releaser)
    listener = PVListener(args.data_pv, new_data_hook)
    listener.start()
    cothread.WaitForQuit()


if __name__ == '__main__':
    main()
