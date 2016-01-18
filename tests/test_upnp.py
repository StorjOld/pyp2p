from pyp2p.upnp import *
from unittest import TestCase


class testUPNP(TestCase):
    def test_upnp(self):
        try:
            assert (UPnP().forward_port("TCP", 50500, get_lan_ip()) is None)
        except Exception as e:
            print(e)
            assert ("Unable to find UPnP compatible gateway" in str(e) or
                    "Failed to add port" in str(e))
