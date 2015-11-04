from unittest import TestCase
from pyp2p.lib import *
from pyp2p.ipgetter import myip
import random


class test_ip_getter(TestCase):
    def test_myip(self):
        ip = get_wan_ip()
        assert (is_ip_valid(ip))
        if sys.version_info >= (3, 0, 0):
            assert (type(ip) == str)
        else:
            assert (type(ip) == unicode)
