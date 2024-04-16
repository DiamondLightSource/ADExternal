#!/usr/bin/env python
import os
import socket
import time

from unittest.mock import MagicMock, patch

from injectfrompv import SharedMem, SocketServer, PVListener


def test_SharedMem():
    shm = SharedMem('test_shm', 1024)
    assert shm.alloc(100) == 0
    assert shm.alloc(100) == 100
    assert shm.alloc(8100) == None
    view = shm.get_view(0)
    assert len(view) == 100
    view[0] = ord(' ')
    view = shm.get_view(100)
    view[1] = ord('x')
    with open('/dev/shm/test_shm', 'rb') as fhandle:
        data = fhandle.read(102)
        assert data == b' ' + b'\x00' * 100 + b'x'


def test_SocketServer():
    socket_path = '/tmp/test_socket'
    socket_server = SocketServer(socket_path, None, None, False)
    socket_server.start()
    assert os.path.exists(socket_path)
    assert socket_server.client is None
    assert socket_server.recv_json() is None
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET, 0)
    sock.connect(socket_path)
    sock.send(b'{"field": 42}')
    while socket_server.client is None:
        time.sleep(0.1)

    msg = socket_server.recv_json()
    assert msg
    assert msg['field'] == 42
    sock.close()
    socket_server.destroy()


@patch('cothread.catools.camonitor')
def test_PVListener(camonitor):
    fun = MagicMock()
    pv_listener = PVListener('test_pv', fun)
    assert not camonitor.called
    pv_listener.start()
    assert camonitor.called
    assert not fun.called
    pv_listener.new_data(None)
    assert fun.called_with(None)
