from unittest import TestCase
from pyp2p.lib import *
from pyp2p.sock import *
from pyp2p.rendezvous_client import RendezvousClient
from pyp2p.rendezvous_server import RendezvousFactory, RendezvousProtocol, LineReceiver
import random
from twisted.internet import reactor
from threading import Thread
import time

# if sys.version_info >= (3,0,0):


class TestRendezvousServer(TestCase):
    def test_00001(self):
        from pyp2p.net import rendezvous_servers
        client = RendezvousClient(nat_type="preserving", rendezvous_servers=rendezvous_servers)
        s = client.server_connect()

        # Test boostrap.
        s.send_line("BOOTSTRAP 1")
        nodes = s.recv_line()
        assert("NODES" in nodes)

        # Test source TCP.
        s.send_line("SOURCE TCP")
        src = s.recv_line()
        assert("REMOTE TCP" in src)

        # Doesn't test passive / sim listen
        # fight, accept, candidate, etc...
        # but that is tested in the net tests

        s.close()

    def test_protocol_messages(self):
        lan_ip = get_lan_ip()

        def run_rendezvous_server():
            try:
                print("Starting rendezvous srever")
                factory = RendezvousFactory()
                reactor.listenTCP(8001, factory, interface=lan_ip)
                reactor.run()
            except Exception as e:
                print(parse_exception(e))
                pass

        Thread(target=run_rendezvous_server).start()
        print("Ready")
        time.sleep(2)
        print(lan_ip)
        sock = Sock(lan_ip, 8001, blocking=1)
        assert(sock.connected)

        # Test bootstrap.
        sock.send_line("BOOTSTRAP 5")
        nodes = sock.recv_line()
        print(nodes)
        assert("NODES" in nodes)

        # Test passive ready.
        sock.send_line("PASSIVE READY 8001 100")

        # Test simultaneous ready.
        sock.send_line("SIMULTANEOUS READY 0 100")

        # Test get remote port.
        sock.send_line("SOURCE TCP")
        ret = sock.recv_line()
        assert("REMOTE" in ret)

        # Test candidate.
        msg = "CANDIDATE %s TCP 3232 2345 2245" % (lan_ip)
        sock.send_line(msg)
        ret = sock.recv_line()
        assert("PREDICTION" in ret)
        ret = sock.recv_line()
        assert("CHALLENGE" in ret)

        # Test accept.
        msg = "ACCEPT %s 3423 23423 34 TCP %s" % (lan_ip, str(time.time()))
        sock.send_line(msg)
        ret = sock.recv_line()
        assert("FIGHT" in ret)

        # Test clear.
        sock.send_line("CLEAR")

        # Test quit.
        sock.send_line("QUIT")

        # Cleanup.
        sock.close()
        reactor.stop()