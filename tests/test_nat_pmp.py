from unittest import TestCase
from pyp2p.lib import *
from pyp2p.nat_pmp import *

class test_nat_pmp(TestCase):
    def test_00001(self):
        try:
            assert(NatPMP().forward_port("TCP", 50500, get_lan_ip()) == None)
        except Exception as e:
            print(e)
            assert("does not support NAT-PMP" in str(e))