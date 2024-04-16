#!/usr/bin/env python

import argparse
import logging
import matplotlib
import sys

from matplotlib import pyplot as plt

from ADExternalPlugin import ADExternalPlugin


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'socket_path', help='Path to unix socket to talk to AD plugin')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()


class ShowOneImage(ADExternalPlugin):
    def __init__(self, socket_path):
        params = {}
        plt.figure()
        ADExternalPlugin.__init__(self, socket_path, params)

    def process_array(self, arr, attr):
        self.close()
        plt.imshow(arr)
        plt.show()
        sys.exit(0)


if __name__ == '__main__':
    args = parse_args()
    matplotlib.use('Qt5Agg')
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    ShowOneImage(args.socket_path).run()
