from unittest import TestCase
from pyp2p.lib import *
from pyp2p.dht_msg import DHT
from pyp2p.net import *
import random
from threading import Thread
import time

class test_net(TestCase):
    def test_00000004(self):
        # Test broadcast.
        nodes = [
            {
                "port": 40001,
                "net": None,
                "thread": None
            },
            {
                "port": 40002,
                "net": None,
                "thread": None
            },
            {
                "port": 40003,
                "net": None,
                "thread": None
            }
        ]

        def accept_cons(node):
            while node["net"] != None:
                for con in node["net"]:
                    x = 1

                time.sleep(0.5)

        # Buld networks.
        for node in nodes:
            node["net"] = Net(net_type="direct", node_type="passive", passive_port=node["port"], debug=1)
            node["net"].disable_forwarding()
            node["net"].disable_bootstrap()
            node["net"].disable_advertise()
            node["net"].enable_duplicate_ip_cons = 1
            node["net"].start()
            node["thread"] = Thread(target=accept_cons, args=(node,))
            node["thread"].start()

        """
        Make connections.
        Note: duplicate connections will be rejected resulting in just one connection from one node to the other nodes.
        """
        for our_node in nodes:
            for their_node in nodes:
                # Don't connect to ourself.
                if our_node == their_node:
                    continue

                # Connect to them.
                our_node["net"].add_node(get_lan_ip(), their_node["port"], "passive")

        # Accept cons:
        for node in nodes:
            node["net"].synchronize()

        # Check connection no.
        for node in nodes:
            assert(len(node["net"]) >= 3)

        # Test broadcast.
        for node in nodes:
            node["net"].broadcast("test")

        # Check for broadcast response on node sockets
        # (Should be on all of them because of duplicate cons.
        for node in nodes:
            for con in node["net"]:
                con.set_blocking(blocking=1, timeout=5)
                line = con.recv_line()
                assert(con.connected)
                assert(line == "test")

        # Close cons.
        for node in nodes:
            for con in node["net"]:
                con.close()

            node["net"].stop()

            # And ... stop threads.
            node["net"] = None

    def test_00000001(self):
       # Test seen messages
        from pyp2p.net import rendezvous_servers
        net = Net(debug=1, nat_type="preserving", node_type="simultaneous", net_type="direct")
        net.disable_advertise()
        net.disable_bootstrap()
        net.disable_duplicates()
        net.start()
        con = net.add_node(rendezvous_servers[0]["addr"], rendezvous_servers[0]["port"], "passive")

        # Test source TCP.
        con.send_line("SOURCE TCP")
        con.send_line("SOURCE TCP 0")
        time.sleep(2)
        replies = []
        for reply in con:
            replies.append(reply)

        print(replies)
        assert(len(replies) >= 1)

        # Disable duplicates.
        clear_seen_messages()
        net.enable_duplicates = 1
        con.send_line("SOURCE TCP")
        con.send_line("SOURCE TCP 0")
        time.sleep(2)
        replies = []
        for reply in con:
            replies.append(reply)

        assert(len(replies) == 2)

    def test_00000003(self):
        # Test validate node
        net = Net(debug=1)
        net.disable_advertise()
        net.disable_bootstrap()
        assert(net.validate_node("127.0.0.1") != 1)
        assert(net.validate_node("0.0.0.0") != 1)
        assert(net.validate_node(get_lan_ip()) != 1)
        assert(net.validate_node(get_lan_ip(), net.passive_port) != 1)
        assert(net.validate_node(net.passive_bind) != 1)
        assert(net.validate_node(net.passive_bind, net.passive_port) != 1)
        assert(net.validate_node(get_wan_ip()) != 1)
        assert(net.validate_node("8.8.8.8"))
        assert(net.validate_node("8.8.8.8", 80000) != 1)
        net.stop()

    def test_00000002(self):
        from pyp2p.net import forwarding_servers
        net = Net(debug=1, nat_type="preserving", node_type="simultaneous", net_type="direct")
        net.disable_advertise()
        net.disable_bootstrap()
        net.start()

        # Test passive outbound connection.
        net.add_node(forwarding_servers[0]["addr"], forwarding_servers[0]["port"], "passive")
        assert(len(net.outbound) == 1)
        assert(net.get_connection_no() == 1)

        # 162.218.239.6

        def threaded_add_node(node_ip, node_port, node_type, net, events):
            def add_node(node_ip, node_port, node_type, net, events):
                con = net.add_node(node_ip, node_port, node_type)
                if con != None:
                    events["success"](con)

            t = Thread(target=add_node, args=(node_ip, node_port, node_type, net, events))
            t.start()

        cons = []
        def success_wrapper(cons):
            def success(con):
                print("Punching succeeded for add_node")
                cons.append(con)

            return success

        events = {
            "success": success_wrapper(cons)
        }

        # Test active simultaneous connection.
        # NAT punching node 1:
        timeout = time.time() + 15
        threaded_add_node("192.187.97.131", 0, "simultaneous", net, events)
        while not len(cons) and time.time() <= timeout:
            time.sleep(1)

        if not len(cons):
            timeout = time.time() + 15
            threaded_add_node("162.218.239.6", 0, "simultaneous", net, events)

            while not len(cons) and time.time() < timeout:
                time.sleep(1)

        if len(cons):
            for con in cons:
                con.close()
        else:
            assert(0)

        def failure_notify(con):
            assert(0)

        def success_notify(con):
            con.close()

        # Test threading hasn't broken the timing.
        events = {
            "failure": failure_notify,
            "success": success_notify
        }

        # This is the not-NATed test node.
        net.unl.connect("AQAAAAAAAAAAAAAAAAAAAAAAAAAAc2dtRMUG79qiBu/aokibQVYAAAAAf0rrLqoubS0=", events)

        assert(net.validate_node(forwarding_servers[0]["addr"], forwarding_servers[0]["port"]))

        net.stop()

    def test_queued_sim_open(self):
        # Test add node.
        net = Net(debug=1, nat_type="preserving", node_type="simultaneous", net_type="direct")
        net.disable_advertise()
        net.disable_bootstrap()
        net.start()

        net.unl.connect("AQAAAAAAAAAAAAAAAAAAAAAAAAAAc2dtRMUG79qiBu/aoqg7O1YAAAAAGkXKuVrNDYE=", events=None)
        net.unl.connect("AQAAAAAAAAAAAAAAAAAAAAAAAAAAc2dtRMWDYbvALwOowGU8O1YAAAAATYLXRfdc5tc=", events=None)
        time.sleep(2)
        assert(len(net.unl.pending_sim_open) == 2)
        net.stop()

