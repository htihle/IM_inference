import numpy as np
import numpy.fft as fft


class MapObj:
    """
    Class for the map-objects which carry the info about the maps and
    also the maps themselves.
    Should in the future also contain info about pixel size, FWHM,
    frequencies etc.
    """
    def __init__(self, exp_param):
        self.exp_param = exp_param
        self.x = exp_param.x
        self.y = exp_param.y
        self.z = exp_param.z
        self.n_x = len(self.x) - 1
        self.n_y = len(self.y) - 1
        self.n_z = len(self.z) - 1
        self.dx = self.x[1] - self.x[0]
        self.dy = self.y[1] - self.y[0]
        self.dz = self.z[1] - self.z[0]
        self.volume = ((self.x[-1] - self.x[0])
                       * (self.y[-1] - self.y[0])
                       * (self.z[-1] - self.z[0])
                       )
        self.vox_vol = self.volume / (self.n_x * self.n_y * self.n_z)
        self.fx = fft.fftshift(fft.fftfreq(self.n_x, self.dx))
        self.fy = fft.fftshift(fft.fftfreq(self.n_y, self.dy))
        self.fz = fft.fftshift(fft.fftfreq(self.n_z, self.dz))
        self.map = None

    def calculate_observables(self, Observables):
        for observable in Observables:
            observable.calculate_observable(self)
