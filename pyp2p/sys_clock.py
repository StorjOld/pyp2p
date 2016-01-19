"""
Given an NTP accurate time, this module computes an
approximation of how far off the system clock is
from the NTP time (clock skew.) The algorithm was
taken from gtk-gnutella.

https://github.com/gtk-gnutella/gtk-gnutella/
blob/devel/src/core/clock.c 
"""


from decimal import Decimal

from .lib import *


class SysClock:
    def __init__(self, clock_skew=Decimal("0")):
        self.enough_data = 40
        self.min_data = 20
        self.max_sdev = 60
        self.clean_steps = 3
        self.data_points = []
        self.clock_skew = clock_skew
        if not self.clock_skew:
            self.collect_data_points()
            self.clock_skew = self.calculate_clock_skew()

    def time(self):
        return Decimal(time.time()) - self.clock_skew

    def collect_data_points(self):
        while len(self.data_points) < self.enough_data + 10:
            clock_skew = Decimal(time.time()) - Decimal(get_ntp())
            self.data_points.append(clock_skew)

    def statx_n(self, data_points):
        return len(data_points)

    def statx_avg(self, data_points):
        total = Decimal("0")
        n = self.statx_n(data_points)
        for i in range(0, n):
            total += data_points[i]

        return total / Decimal(n)

    def statx_sdev(self, data_points):
        def _ss(data):
            """Return sum of square deviations of sequence data."""
            c = self.statx_avg(data)
            ss = sum((x-c)**2 for x in data)
            return ss

        def pstdev(data):
            """Calculates the population standard deviation."""
            n = len(data)
            if n < 2:
                raise ValueError('variance requires at least two data points')
            ss = _ss(data)
            pvar = ss/n  # the population variance
            return pvar**Decimal("0.5")

        return pstdev(data_points)

    def calculate_clock_skew(self):
        """
        Computer average and standard deviation
        using all the data points.
        """
        n = self.statx_n(self.data_points)

        """
        Required to be able to compute the standard
        deviation.
        """
        if n < 1:
            return Decimal("0")

        avg = self.statx_avg(self.data_points)
        sdev = self.statx_sdev(self.data_points)

        """
        Incrementally remove aberration points.
        """
        for k in range(0, self.clean_steps):
            """
            Remove aberration points: keep only
            the sigma range around the average.
            """
            min_val = avg - sdev
            max_val = avg + sdev

            cleaned_data_points = []
            for i in range(0, n):
                v = self.data_points[i]
                if v < min_val or v > max_val:
                    continue
                cleaned_data_points.append(v)

            self.data_points = cleaned_data_points[:]

            """
            Recompute the new average using the
            "sound" points we kept.
            """
            n = self.statx_n(self.data_points)

            """
            Not enough data to compute standard
            deviation.
            """
            if n < 2:
                break

            avg = self.statx_avg(self.data_points)
            sdev = self.statx_sdev(self.data_points)

            if sdev <= self.max_sdev or n < self.min_data:
                break

        """
        If standard deviation is too large still, we
        cannot update our clock. Collect more points.

        If we don't have a minimum amount of data,
        don't attempt the update yet, continue collecting.
        """
        if sdev > self.max_sdev or n < self.min_data:
            return Decimal("0")

        return avg
        
if __name__ == "__main__":
    sys_clock = SysClock()
    print(sys_clock.clock_skew)

    while 0:
        sys_clock = SysClock()
        ntp = Decimal(get_ntp())
        adjusted = sys_clock.time()
        dif = ntp - adjusted
        if dif < 0:
            dif = -dif

        print(dif)
        if dif < 0.05:
            break

    # print(get_ntp())
    # print(get_ntp())

    """
    print(sys_clock.time())
    print()
    print(get_ntp())
    print(sys_clock.time())
    print()
    print(get_ntp())
    print(sys_clock.time())
    """

