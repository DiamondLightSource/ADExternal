#!/usr/bin/env python

import argparse
import json
import logging
import zmq

from importlib import import_module

from ADExternalPlugin import ADExternalPlugin, ATTRS_FIELD, PARAMS_FIELD


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'socket_path', help='Path to unix socket to talk to AD plugin')
    parser.add_argument(
        'class_name', help='Worker class we will instantiate and interpose')
    parser.add_argument(
        'endpoint', help='ZMQ endpoint to send frame information')
    parser.add_argument(
        '--with-frame-data', action='store_true', help='Send frame data too')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()


# this plugin forwards the frame information in a ZMQ multipart message,
# first part contains the metada of the input frame,
# second part contains the metadata of the output frame and
# third part can be empty or contain the frame data
class ZmqForwarder(ADExternalPlugin):
    def __init__(self, target_plugin, socket_path, endpoint, forward_data=True,
                 initial_params={}):
        ADExternalPlugin.__init__(self, socket_path, initial_params)
        self.target_plugin = target_plugin
        self.endpoint = endpoint
        self.forward_data = forward_data
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUSH)
        self.socket.connect(self.endpoint)
        self.set_post_process_hook(self.post_process)
        # we are impersonating that plugin
        self.name = target_plugin.__class__.__name__

    def on_connected(self, params):
        target_plugin.on_connected(params)

    def params_changed(self, params):
        target_plugin.params_changed(params)

    def post_process(self, arr, in_msg, out_msg):
        self.socket.send_json(in_msg, flags=zmq.SNDMORE)
        self.socket.send_json(out_msg, flags=zmq.SNDMORE)
        if self.forward_data:
            self.socket.send(memoryview(arr))
        else:
            self.socket.send(b'')

    def pop_new_params(self):
        return target_plugin.pop_new_params()

    def process_array(self, arr, attrs):
        out_arr = target_plugin.process_array(arr, attrs)
        return out_arr


if __name__ == '__main__':
    args = parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    target_module = import_module(args.class_name)
    target_class = getattr(target_module, args.class_name)
    target_plugin = target_class(args.socket_path)
    ZmqForwarder(target_plugin, args.socket_path, args.endpoint,
                 args.with_frame_data).run()
