#!/dls_sw/prod/python3/RHEL7-x86_64/fit_lib/1.4/lightweight-venv/bin/python
import argparse
import logging
import time

from ADExternalPlugin import ADExternalPlugin


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


class StepControl(object):
    def __init__(self, init_step, min_val, max_val):
        self.set_parameters(init_step, min_val, max_val)

    def set_parameters(self, init_step, min_val, max_val):
        self.init_step = init_step
        self.min_val = min_val
        self.max_val = max_val
        self.next_step = init_step
        self.max_step = type(init_step)(abs(max_val - min_val) / 2)
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


class AutoExposure(ADExternalPlugin):
    def __init__(self, socket_path):
        # default values if server doesn't send us updated ones
        params = dict(iEnableAutoExposure=0,
                      dExposure=0.0,
                      dExposureSp=0.0,
                      dMinExposure=0.0,
                      dMaxExposure=2.0,
                      dInitialStep=0.01,
                      iMaxPixelMax=254,
                      iMaxPixelMin=210,
                      dAdjustPeriod=2.0,
                      iMaxPixelValue=0)
        self.step_control = StepControl(
                params['dInitialStep'], params['dMinExposure'],
                params['dMaxExposure'])
        self.last_adjust_ts = time.time()
        self.last_exp_sp = 0.0
        ADExternalPlugin.__init__(self, socket_path, params)

    def on_connected(self, params):
        init_step = params.get('dInitialStep', self['dInitialStep'])
        min_val = params.get('dMinExposure', self['dMinExposure'])
        max_val = params.get('dMaxExposure', self['dMaxExposure'])
        self.step_control.set_parameters(init_step, min_val, max_val)

    def params_changed(self, params):
        for key in ('dInitialStep', 'dMinExposure', 'dMaxExposure'):
            if key in params:
                self.on_connected(params)
                return

    def process_array(self, arr, attr={}):
        max_pixel = arr.max()
        self['iMaxPixelValue'] = int(max_pixel)
        # 0 disabled, 1 enabled
        if self['iEnableAutoExposure'] \
                and self.last_adjust_ts + self['dAdjustPeriod'] <= time.time():
            self.last_adjust_ts = time.time()
            direction = \
                1 if max_pixel < self['iMaxPixelMin'] else \
                -1 if max_pixel > self['iMaxPixelMax'] else \
                0
            exp_sp = self.step_control.updated_value(self['dExposure'],
                                                     direction)
            self.log.debug(
                'AutoExposure: max_pixel=%d, direction=%d, setpoint=%f',
                max_pixel, direction, exp_sp)
            if direction != 0 and self.last_exp_sp != exp_sp:
                self['dExposureSp'] = exp_sp
                self.last_exp_sp = exp_sp

        return arr


if __name__ == "__main__":
    args = parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    AutoExposure(args.socket_path).run()
