#!/dls_sw/prod/python3/RHEL7-x86_64/fit_lib/1.4/lightweight-venv/bin/python
import argparse
import logging

import numpy

from fit_lib import fit_lib
from fit_lib.fit_lib import doFit2dGaussian, doFit2dGaussian_0, convert_abc
from fit_lib.levmar import FitError

from ADExternalPlugin import ADExternalPlugin

import scipy.ndimage


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'socket_path', help='Path to unix socket to talk to AD plugin')
    parser.add_argument('--debug', action='store_true')
    return parser.parse_args()


def restrict(val, min_val, max_val):
    if val < min_val:
        return min_val

    if val > max_val:
        return max_val

    return val


class AutoExposureControl(object):
    def __init__(self, init_step, min_val, max_val):
        self.set_parameters(init_step, min_val, max_val)

    def set_parameters(self, init_step, min_val, max_val):
        self.init_step = init_step
        self.min_val = min_val
        self.max_val = max_val
        self.next_step = init_step
        self.max_step = abs(max_val - min_val)
        self.init_step = init_step
        self.last_direction = 0

    def updated_value(self, current, direction=0):
        # update direction: 1 up -1 down 0 stand
        if direction == 0 or direction != self.last_direction:
            step = self.init_step
            self.next_step = self.init_step
        else:  # direction == self.last_direction
            step = self.next_step
            self.next_step = min(2 * self.next_step, self.max_step)

        new_value = restrict(
            current + direction*step, self.min_val, self.max_val)
        self.last_direction = direction
        return new_value


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
                      sFitStatus="",
                      iFitType=-1,
                      iEnableFilter=0,
                      iEnableAutoExposure=0,
                      dExposure=0.0,
                      dExposureSp=0.0,
                      dMinExposure=0.0,
                      dMaxExposure=2.0,
                      iMaxPixelMax=254,
                      iMaxPixelMin=210,
                      dInitialStep=0.01,
                      iMinPixelLevel=10,
                      iFit0Enabled=0
                      )
        self.auto_exposure = AutoExposureControl(
                params['dInitialStep'], params['dMinExposure'],
                params['dMaxExposure'])
        self.fitting_function = doFit2dGaussian
        ADExternalPlugin.__init__(self, socket_path, params)
        self.frame_counter = 0
        self.last_exp_sp = 0

    def on_connected(self, params):
        init_step = params.get('dInitialStep', self['dInitialStep'])
        min_val = params.get('dMinExposure', self['dMinExposure'])
        max_val = params.get('dMaxExposure', self['dMaxExposure'])
        fit0enabled = params.get('iFit0Enabled', self['iFit0Enabled'])
        self.auto_exposure.set_parameters(init_step, min_val, max_val)
        self.fitting_function = \
            doFit2dGaussian_0 if fit0enabled else doFit2dGaussian

    def params_changed(self, params):
        for key in ('dInitialStep', 'dMinExposure',
                    'dMaxExposure', 'iFit0Enabled'):
            if key in params:
                self.on_connected(params)
                return

    def reset_results(self):
        self["iFitType"] = 0
        self["dBaseline"] = 0.0
        self["iPeakHeight"] = 0
        self["iOriginX"] = 0
        self["iOriginY"] = 0
        self["dSigmaX"] = 0.0
        self["dSigmaY"] = 0.0
        self["dAngle"] = 0.0
        self["dError"] = 0.0

    def do_fit(self, arr):
        try:
            fit, error = self.fitting_function(
                arr, thinning=(self["iFitThinning"], self["iFitThinning"]),
                window_size=self["iFitWindowSize"], maxiter=self["iMaxiter"],
                ROI=None, gamma=None, extra_data=False)

            # fit outputs in terms of ABC we want sigma x, sigma y and angle.
            s_x, s_y, th = convert_abc(*fit[4:7])
            if any([fit[i+2] < -arr.shape[i]
                    or fit[i+2] > 2*arr.shape[i] for i in [0, 1]]):
                raise FitError("Fit out of range")

            self["sFitStatus"] = "Gaussian Fit OK"
            self["iFitType"] = 0
            self["dBaseline"] = float(fit[0])
            self["iPeakHeight"] = int(fit[1])
            self["iOriginX"] = int(fit[2])
            self["iOriginY"] = int(fit[3])
            self["dSigmaX"] = s_x
            self["dSigmaY"] = s_y
            self["dAngle"] = th
            self["dError"] = float(error)
        except FitError as e:
            self["sFitStatus"] = "Fit error: %s" % (e,)
            self["iFitType"] = -1
            self.reset_results()
        except Exception as e:
            self["sFitStatus"] = "error: %s" % (e,)
            self["iFitType"] = -1
            self.reset_results()

    def process_array(self, arr, attr={}):
        # Convert the array to a float so that we do not overflow during
        # processing.
        arr2 = numpy.float_(arr)
        # Run a median filter over the image to remove the spikes due to dead
        # pixels.
        if self['iEnableFilter']:
            arr2 = scipy.ndimage.median_filter(arr2, size=3)

        max_pixel = arr2.max()

        if max_pixel >= self['iMinPixelLevel']:
            self.do_fit(arr2)
        else:
            self["sFitStatus"] = "error: image too dim"
            self["iFitType"] = -1
            self.reset_results()

        # Write the attibute array which will be attached to the output array.
        # Note that we convert from the numpy
        # uint64 type to a python integer as we only handle python integers,
        # doubles and strings in the C code for now
        # Fitter results
        for param in self:
            attr[param] = self[param]

        self.log.debug(
            "Array processed, baseline: %f, peak height: %d, origin x: %d, " +
            "origin y: %d, sigma x: %f, sigma y: %f, angle: %f, error: %f",
            self["dBaseline"], self["iPeakHeight"], self["iOriginX"],
            self["iOriginY"], self["dSigmaX"], self["dSigmaY"],
            self["dAngle"], self["dError"]
        )

        # 0 disabled, 1 enabled, > 1 means do each 'iEnableAutoExposure' frames
        if self['iEnableAutoExposure'] \
                and self.frame_counter % self['iEnableAutoExposure'] == 0:
            direction = 1 if max_pixel < self['iMaxPixelMin'] else \
                       -1 if max_pixel > self['iMaxPixelMax'] else \
                       0
            exp_sp = self.auto_exposure.updated_value(self['dExposure'],
                                                      direction)
            self.log.debug(
                'AutoExposure: max_pixel=%d, direction=%d, setpoint=%f',
                max_pixel, direction, exp_sp)
            if direction != 0 and self.last_exp_sp != exp_sp:
                self['dExposureSp'] = exp_sp
                self.last_exp_sp = exp_sp

        self.frame_counter += 1
        # return the resultant array.
        return arr


if __name__ == "__main__":
    args = parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    Gaussian2DFitter(args.socket_path).run()
