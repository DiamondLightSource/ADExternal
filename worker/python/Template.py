#!/dls_sw/prod/python3/RHEL7-x86_64/pymalcolm/6.2/lightweight-venv/bin/python
from numpy import add

from ADExternalPlugin import ADExternalPlugin

MODE_NOCOPY = 0
MODE_COPY = 1
MODE_DONOTHING = 2


class Template(ADExternalPlugin):
    def __init__(self, dont_copy=True):
        params = {
            'iInt1': 100,
            'sInt1Name': 'Array offset',
            'iInt2': 2,
            'sInt2Name': 'Array Sum',
            'iInt3': 0,
            'sInt3Name': 'Mode (0 no copy, 1 copy, 2 do nothing)',
        }
        ADExternalPlugin.__init__(self, params)
        self.dont_copy = dont_copy

    def paramChanged(self):
        # one of our input parameters has changed
        # just log it for now, do nothing.
        self.log.debug("Parameter has been changed %s", self)

    def processArray(self, arr, attr={}):
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
    Template().run()
