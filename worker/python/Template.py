#!/dls_sw/prod/python3/RHEL7-x86_64/pymalcolm/6.2/lightweight-venv/bin/python
import argparse
import logging

from numpy import add

from ADExternalPlugin import ADExternalPlugin

MODE_NOCOPY = 0
MODE_COPY = 1
MODE_DONOTHING = 2


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'socket_path', help='Path to unix socket to talk to AD plugin')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()


class Template(ADExternalPlugin):
    def __init__(self, socket_path):
        # values used before getting updated ones from server
        params = {
            'iInt1': 100,
            'sInt1Name': 'Array offset',
            'iInt2': 2,
            'sInt2Name': 'Array Sum',
            'iInt3': 0,
            'sInt3Name': 'Mode (0 no copy, 1 copy, 2 do nothing)',
        }
        ADExternalPlugin.__init__(self, socket_path, params)

    def params_changed(self, new_params):
        # one of our input parameters has changed
        # just log it for now, do nothing.
        self.log.debug("Parameter has been changed %s", new_params)

    def process_array(self, arr, attr={}):
        if self['iInt3'] == MODE_DONOTHING:
            return arr

        if self['iInt3'] == MODE_NOCOPY:
            arr += self['iInt1']
        else:  # MODE_COPY
            arr = add(arr, self['iInt1'])

        # doubles and strings in the C code for now
        attr['sum'] = int(arr.sum())
        self['iInt2'] = attr['sum']
        self.log.debug('Array processed, sum: %d', attr['sum'])

        # return the resultant array.
        return arr


if __name__ == '__main__':
    args = parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    Template(args.socket_path).run()
