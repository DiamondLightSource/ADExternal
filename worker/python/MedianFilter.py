#!/dls_sw/prod/python3/RHEL7-x86_64/fit_lib/1.4/lightweight-venv/bin/python
import argparse
import logging

from ADExternalPlugin import ADExternalPlugin
import scipy.ndimage


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'socket_path', help='Path to unix socket to talk to AD plugin')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()


class MedianFilter(ADExternalPlugin):
    tempCounter = 0

    def __init__(self, socket_path):
        # default values if server doesn't send us updated ones
        params = dict(iMedianFilterSize=0)
        ADExternalPlugin.__init__(self, socket_path, params)

    def process_array(self, arr, attr):
        if self['iMedianFilterSize']:
            return scipy.ndimage.median_filter(
                arr, size=self['iMedianFilterSize'])
        else:
            return arr


if __name__ == "__main__":
    args = parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    MedianFilter(args.socket_path).run()
