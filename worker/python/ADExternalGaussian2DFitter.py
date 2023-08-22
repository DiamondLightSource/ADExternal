#!/dls_sw/prod/python3/RHEL7-x86_64/fit_lib/1.4/lightweight-venv/bin/python

import logging
import numpy

from fit_lib import fit_lib
from fit_lib.fit_lib import doFit2dGaussian, convert_abc
from fit_lib.levmar import FitError

from ADExternalPlugin import ADExternalPlugin

import scipy.ndimage


class Gaussian2DFitter(ADExternalPlugin):
    tempCounter = 0
    def __init__(self):
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
                      iEnableFilter=0
                      )
        ADExternalPlugin.__init__(self, params)

    def processArray(self, arr, attr={}):
        failed = False
        # Convert the array to a float so that we do not overflow during processing.
        arr2 = numpy.float_(arr)
        # Run a median filter over the image to remove the spikes due to dead
        # pixels.
        if self['iEnableFilter']:
            arr2 = scipy.ndimage.median_filter(arr2, size=3)

        try:
            self.log.debug(
                "thinning %d windows %d max iter %d", self["iFitThinning"],
                self["iFitWindowSize"], self["iMaxiter"])
            fit, error = doFit2dGaussian(
                arr2, thinning=(self["iFitThinning"], self["iFitThinning"]),
                window_size=self["iFitWindowSize"], maxiter=self["iMaxiter"],
                ROI=None, gamma=None, extra_data=False)

            # fit outputs in terms of ABC we want sigma x, sigma y and angle.
            s_x, s_y, th = convert_abc(*fit[4:7])
            if any([fit[i+2] < -arr2.shape[i] or fit[i+2] > 2*arr2.shape[i] for i in [0, 1]]):
                raise FitError("Fit out of range")
            self["sFitStatus"] = "Gaussian Fit OK"
            self["iFitType"] = 0
        except FitError as e:
            self["sFitStatus"] = "Fit error: %s" % (e,)
            self["iFitType"] = -1
            failed = True
        except Exception as e:
            self["sFitStatus"] = "error: %s" % (e,)
            self["iFitType"] = -1
            failed = True

        if failed:
            cx, cy, s_x, s_y, h0 = [0]*5
            th = 0.0
            fit = [0.0, h0, cx, cy]
            error = 0.0
            results = None
            s_x = 1.0
            s_y = 1.0

        # Write out to the EDM output parameters.
        self["dBaseline"] = float(fit[0])
        self["iPeakHeight"] = int(fit[1])
        self["iOriginX"] = int(fit[2])
        self["iOriginY"] = int(fit[3])
        self["dSigmaX"] = s_x
        self["dSigmaY"] = s_y
        self["dAngle"] = th
        self["dError"] = float(error)

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
        # return the resultant array.
        return arr


if __name__=="__main__":
    Gaussian2DFitter().run()
