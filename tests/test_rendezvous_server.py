from unittest import TestCase
from pyp2p.lib import *
from pyp2p.sock import *
import random

#if sys.version_info >= (3,0,0):

class test_rendezvous_client(TestCase):
    def test_00001(self):
        from pyp2p.net import rendezvous_servers
        s = Sock(rendezvous_servers[0]["addr"], rendezvous_servers[0]["port"], blocking=1)

        #Test boostrap.
        s.send_line("BOOTSTRAP 1")
        nodes = s.recv_line()
        assert("NODES" in nodes)

        #Test source TCP.
        s.send_line("SOURCE TCP")
        src = s.recv_line()
        assert("REMOTE TCP" in src)

        #Doesn't test passive / sim listen
        #fight, accept, candidate, etc...
        #but that is tested in the net tests

        s.close()

