#!/usr/bin/env python

import argparse
import logging

import numpy

from fit_lib import fit_lib
from fit_lib.fit_lib import doFit2dGaussian, doFit2dGaussian_0, convert_abc
from fit_lib.levmar import FitError

from ADExternalPlugin import ADExternalPlugin


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'socket_path', help='Path to unix socket to talk to AD plugin')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()


class Gaussian2DFitter(ADExternalPlugin):
    tempCounter = 0

    def __init__(self, socket_path):
        # default values if server doesn't send us updated ones
        params = dict(iPeakHeight=1,
                      iOriginX=2,
                      iOriginY=3,
                      dBaseline=3.,
                      dSigmaX=1.0,
                      dSigmaY=2.0,
                      dAngle=3.0,
                      dError=2.0,
                      iFitWindowSize=3,
                      iFitThinning=5,
                      iMaxiter=20,
                      sFitStatus='',
                      iFitType=-1,
                      dMinPixelLevel=0.0,
                      iFit0Enabled=0,
                      dA=0.0,
                      dB=0.0,
                      dC=0.0)
        self.fitting_function = doFit2dGaussian
        ADExternalPlugin.__init__(self, socket_path, params)

    def on_connected(self, params):
        fit0enabled = params.get('iFit0Enabled', self['iFit0Enabled'])
        self.fitting_function = \
            doFit2dGaussian_0 if fit0enabled else doFit2dGaussian

    def params_changed(self, params):
        for key in ('iFit0Enabled',):
            if key in params:
                self.on_connected(params)
                return

    def reset_results(self):
        self['iFitType'] = 0
        self['dBaseline'] = 0.0
        self['iPeakHeight'] = 0
        self['iOriginX'] = 0
        self['iOriginY'] = 0
        self['dSigmaX'] = 0.0
        self['dSigmaY'] = 0.0
        self['dAngle'] = 0.0
        self['dError'] = 0.0

    def do_fit(self, arr):
        try:
            fit, error = self.fitting_function(
                arr, thinning=(self['iFitThinning'], self['iFitThinning']),
                window_size=self['iFitWindowSize'], maxiter=self['iMaxiter'],
                ROI=None, gamma=None, extra_data=False)

            # fit outputs in terms of ABC we want sigma x, sigma y and angle.
            s_x, s_y, th = convert_abc(*fit[4:7])
            if any([fit[i+2] < -arr.shape[i]
                    or fit[i+2] > 2*arr.shape[i] for i in [0, 1]]):
                raise FitError('Fit out of range')

            self['sFitStatus'] = 'Gaussian Fit OK'
            self['iFitType'] = 0
            self['dBaseline'] = float(fit[0])
            self['iPeakHeight'] = int(fit[1])
            self['iOriginX'] = int(fit[2])
            self['iOriginY'] = int(fit[3])
            self['dA'] = float(fit[4])
            self['dB'] = float(fit[5])
            self['dC'] = float(fit[6])
            self['dSigmaX'] = s_x
            self['dSigmaY'] = s_y
            self['dAngle'] = th
            self['dError'] = float(error)
        except FitError as e:
            self['sFitStatus'] = 'Fit error: %s' % (e,)
            self['iFitType'] = -1
            self.reset_results()
        except Exception as e:
            self['sFitStatus'] = 'Unexpected error: %s' % (e,)
            self['iFitType'] = -1
            self.reset_results()

    def process_array(self, arr, attr):
        # Convert the array to a float so that we do not overflow during
        # processing.
        arr2 = numpy.float_(arr)
        max_pixel_val = arr2.max()

        if max_pixel_val >= self['dMinPixelLevel']:
            self.do_fit(arr2)
        else:
            self['sFitStatus'] = 'Error: image too dim'
            self['iFitType'] = -1
            self.reset_results()

        # Write the attibute array which will be attached to the output array.
        # Note that we convert from the numpy
        # uint64 type to a python integer as we only handle python integers,
        # doubles and strings in the C code for now
        # Fitter results
        for param in self:
            attr[param] = self[param]

        self.log.debug(
            'Array processed, baseline: %f, peak height: %d, origin x: %d, ' +
            'origin y: %d, sigma x: %f, sigma y: %f, angle: %f, error: %f, ' +
            'max_pixel_val: %f',
            self['dBaseline'], self['iPeakHeight'], self['iOriginX'],
            self['iOriginY'], self['dSigmaX'], self['dSigmaY'],
            self['dAngle'], self['dError'], max_pixel_val
        )

        # return the input frame, we are not changing it
        return arr


if __name__ == '__main__':
    args = parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    Gaussian2DFitter(args.socket_path).run()
