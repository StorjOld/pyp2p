from unittest import TestCase
from pyp2p.upnp import *
from pyp2p.lib import *


class test_upnp(TestCase):
    def test_upnp(self):
        try:
            assert (UPnP().forward_port("TCP", 50500, get_lan_ip()) == None)
        except Exception as e:
            assert ("Unable to find UPnP compatible gateway" in str(
                e) or "Failed to add port" in str(e))
