from pyp2p.lib import *
from pyp2p.nat_pmp import *

from unittest import TestCase


class TestNATPMP(TestCase):
    def test_00001(self):
        try:
            assert (NatPMP().forward_port("TCP", 50500, get_lan_ip()) is None)
        except Exception as e:
            print(e)
            assert ("does not support NAT-PMP" in str(e))
