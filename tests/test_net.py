import unittest
from unittest import TestCase

from twisted.internet import reactor

from pyp2p.net import *
from pyp2p.sys_clock import SysClock
from pyp2p.rendezvous_server import RendezvousFactory


class TestNet(TestCase):
    @unittest.skip("Not implemented")
    def test_get_con_by_unl(self):
        pass

    def test_bootstrap_and_challenge(self):
        # Test bootstrap
        # Test challenge protocol for sim open
        # Test rendezvous protocol
        # All in same func due to twisted errors ...
        lan_ip = get_lan_ip()

        def run_rendezvous_server():
            try:
                factory = RendezvousFactory()
                test_ip = "74.125.224.72"
                factory.nodes["passive"][test_ip] = {
                    "ip_addr": test_ip,
                    "port": 80
                }

                reactor.listenTCP(8002, factory, interface=lan_ip)
            except Exception as e:
                print(parse_exception(e))
                pass

        Thread(target=run_rendezvous_server).start()

        def run_rendezvous_server():
            try:
                factory = RendezvousFactory()
                reactor.listenTCP(8003, factory, interface=lan_ip)
            except Exception as e:
                print(parse_exception(e))
                pass

        Thread(target=run_rendezvous_server).start()

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

        time.sleep(2)
        rendezvous_servers = [
            {
                "addr": lan_ip,
                "port": 8002
            }
        ]

        net = Net(
            debug=1,
            net_type="p2p",
            node_type="simultaneous",
            nat_type="preserving",
            passive_port=0,
            servers=rendezvous_servers
        ).start()
        assert net.enable_bootstrap
        net.bootstrap()
        assert(len(net.outbound))
        net.stop()

        time.sleep(2)
        rendezvous_servers = [
            {
                "addr": lan_ip,
                "port": 8003
            }
        ]

        alice = Net(
            debug=1,
            net_type="direct",
            node_type="simultaneous",
            nat_type="preserving",
            passive_port=0,
            servers=rendezvous_servers
        ).start()

        bob = Net(
            debug=1,
            net_type="direct",
            node_type="simultaneous",
            nat_type="preserving",
            passive_port=0,
            servers=rendezvous_servers
        ).start()
        bob.advertise()
        alice.add_node(lan_ip, 0, "simultaneous")
        alice.stop()
        bob.stop()

        print("Ready")
        time.sleep(2)
        print(lan_ip)
        sock = Sock(lan_ip, 8001, blocking=1)
        assert sock.connected

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
        msg = "CANDIDATE %s TCP 3232 2345 2245" % lan_ip
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

    @unittest.skip("Not implemented")
    def test_con_by_id(self):
        pass

    @unittest.skip("Not implemented")
    def test_generate_con_id(self):
        pass

    def test_nat_tcp_hole_punch(self):
        """
        If the test fails the node may actually be down.
        """
        net = Net(
            net_type="direct",
            node_type="simultaneous",
            nat_type="preserving",
            passive_port=48310,
            sys_clock=SysClock()
        ).start()

        connected = 0

        def success_notify(con):
            global connected
            connected = 1
            print("SUCCESS NOTIFY")

        # Test threading hasn't broken the timing.
        events = {
            "success": success_notify
        }

        # This is the NATed test node.
        unl_value = "AnRBam11OG1IUEhGVkRKOHQ3cEs4c2dtRMWDYbvALwOowOEG0lc="
        for i in range(0, 5):
            """
            The reason this test sometimes fails is due to timing: the packets
            need to cross in such a way that the timing for the connects that
            Travis CI makes to the NATed' test node need to arrive -BEFORE- the
            test nodes connect times out otherwise subsequent connects from
            Travis yield RST packets.

            The TCP setup for the NATed test node isn't a true NAT / is typical
            of NATs that are in the wild. Alternatively: the hosts are too
            close.
            """
            net.unl.connect(unl_value, events)

            looping = 1
            future = time.time() + 30
            while time.time() < future:
                # Synchronize.
                for con in net:
                    print("Success")
                    connected = 1
                    future = time.time() - 100
                    break

                time.sleep(0.5)

            if connected:
                break

            time.sleep(10)

        net.stop()

        if not connected:
            assert 0

    def test_net_config(self):
        """
        Tests whether the Net class behaviours as expected relative to manually
        setting networking info and interacting with key functions.

        "enable_bootstrap": "default",
        "enable_advertise": "default",
        "enable_duplicates": "default",
        """

        tests = [
            # P2P, passive, preserving
            {
                "options": {},
                "config": {
                    "net_type": "p2p",
                    "node_type": "passive",
                    "nat_type": "unknown"
                },
                "expected": {
                    "duplicate_cons": 0,
                    "advertise": "self",
                    "bootstrap": "self",
                    "config": {
                        "net_type": "p2p",
                        "node_type": "passive",
                        "nat_type": "!input"
                    }
                }
            },

            # P2P, simultaneous, preserving
            {
                "options": {},
                "config": {
                    "net_type": "p2p",
                    "node_type": "simultaneous",
                    "nat_type": "preserving"
                },
                "expected": {
                    "duplicate_cons": 0,
                    "advertise": "self",
                    "bootstrap": "self",
                    "config": {
                        "net_type": "p2p",
                        "node_type": "active",
                        "nat_type": "preserving"
                    }
                }
            },

            # P2P, unknown, unknown
            {
                "options": {},
                "config": {
                    "net_type": "p2p",
                    "node_type": "unknown",
                    "nat_type": "unknown"
                },
                "expected": {
                    "duplicate_cons": 0,
                    "advertise": "self",
                    "bootstrap": "self",
                    "config": {
                        "net_type": "p2p",
                        "node_type": "!input",
                        "nat_type": "!input"
                    }
                }
            },

            # Direct, unknown, unknown (forwarding disabled.)
            {
                "options": {
                    "enable_forwarding": 0
                },
                "config": {
                    "net_type": "direct",
                    "node_type": "unknown",
                    "nat_type": "unknown"
                },
                "expected": {
                    "duplicate_cons": 1,
                    "advertise": "self",
                    "bootstrap": None,
                    "config": {
                        "net_type": "direct",
                        "node_type": "!input",
                        "nat_type": "!input"
                    }
                }
            },

            # Direct, unknown, random (forwarding disabled.)
            {
                "options": {
                    "enable_forwarding": 0
                },
                "config": {
                    "net_type": "direct",
                    "node_type": "unknown",
                    "nat_type": "random"
                },
                "expected": {
                    "duplicate_cons": 1,
                    "advertise": "self",
                    "bootstrap": None,
                    "config": {
                        "net_type": "direct",
                        "node_type": "!input",
                        "nat_type": "random"
                    }
                }
            },

            # Direct, passive, preserving.
            {
                "options": {},
                "config": {
                    "net_type": "direct",
                    "node_type": "passive",
                    "nat_type": "preserving"
                },
                "expected": {
                    "duplicate_cons": 1,
                    "advertise": None,
                    "bootstrap": None,
                    "config": {
                        "net_type": "direct",
                        "node_type": "passive",
                        "nat_type": "preserving"
                    }
                }
            },

            # Direct, passive, unknown.
            {
                "options": {},
                "config": {
                    "net_type": "direct",
                    "node_type": "passive",
                    "nat_type": "unknown"
                },
                "expected": {
                    "duplicate_cons": 1,
                    "advertise": None,
                    "bootstrap": None,
                    "config": {
                        "net_type": "direct",
                        "node_type": "passive",
                        "nat_type": "!input"
                    }
                }
            },

            # Direct, unknown, unknown.
            {
                "options": {},
                "config": {
                    "net_type": "direct",
                    "node_type": "unknown",
                    "nat_type": "unknown"
                },
                "expected": {
                    "duplicate_cons": 1,
                    "advertise": "unknown",
                    "bootstrap": "unknown",
                    "config": {
                        "net_type": "direct",
                        "node_type": "!input",
                        "nat_type": "!input"
                    }
                }
            },

            # Direct, simultaneous, preserving.
            {
                "options": {},
                "config": {
                    "net_type": "direct",
                    "node_type": "simultaneous",
                    "nat_type": "preserving"
                },
                "expected": {
                    "duplicate_cons": 1,
                    "advertise": "self",
                    "bootstrap": None,
                    "config": {
                        "net_type": "direct",
                        "node_type": "simultaneous",
                        "nat_type": "preserving"
                    }
                }
            },

            # Direct, simultaneous, random.
            {
                "options": {},
                "config": {
                    "net_type": "direct",
                    "node_type": "simultaneous",
                    "nat_type": "random"
                },
                "expected": {
                    "duplicate_cons": 1,
                    "advertise": "self",
                    "bootstrap": None,
                    "config": {
                        "net_type": "direct",
                        "node_type": "active",
                        "nat_type": "random"
                    }
                }
            },

            # Direct, simultaneous, unknown.
            {
                "options": {},
                "config": {
                    "net_type": "direct",
                    "node_type": "simultaneous",
                    "nat_type": "unknown"
                },
                "expected": {
                    "duplicate_cons": 1,
                    "advertise": "self",
                    "bootstrap": None,
                    "config": {
                        "net_type": "direct",
                        "node_type": "simultaneous",
                        "nat_type": "!input"
                    }
                }
            }
        ]

        wan_ip = get_wan_ip()
        test_no = 0
        for test in tests:
            # Separate tests in output.
            print()
            print()
            print()

            # Setup net object.
            config = test["config"]
            net = Net(
                passive_port=50512,
                net_type=config["net_type"],
                node_type=config["node_type"],
                nat_type=config["nat_type"],
                wan_ip=wan_ip
            )

            # Enable any options.
            options = test["options"]
            for name in list(options):
                option = options[name]

                if option == 1 or option == 0:
                    cmd = "net." + name + " = " + str(option)
                    exec(cmd)
                    assert(eval("net." + name) == option)

            # Start networking.
            net.start()

            # Check net is started.
            assert(net is not None)
            assert(net.is_net_started == 1)

            # Check duplicate connections state.
            assert(net.enable_duplicate_ip_cons ==
                   test["expected"]["duplicate_cons"])

            # Check config.
            for key in list(config):
                conf_in = test["config"][key]
                conf_out = test["expected"]["config"][key]
                print(str(test_no) + " Checking config " + str(key))
                print(str(test_no) + " Conf in = " + str(conf_in))
                print(str(test_no) + " Conf out = " + str(conf_out))

                # Check that the net settings changed.
                if conf_out == "!input":
                    assert(conf_out != conf_in)

                # Check the net settings matched what we wanted.
                if conf_out != "!input":
                    found = eval("net." + str(key))
                    assert(conf_out == found)

            # Check the passive server is started.
            if config["node_type"] == "passive":
                assert(net.passive is not None)

            # Setup functions to check.
            functions = {
                "advertise": net.advertise,
                "bootstrap": net.bootstrap
            }

            # Check functions work.
            for func_name in list(functions):
                print(str(test_no) + " Testing " + str(func_name))

                func_body = functions[func_name]
                expected = test["expected"][func_name]
                ret = func_body()
                print(ret)
                if expected == "self":
                    assert(ret == net)

                if expected is None:
                    assert(ret is None)

            # Stop net.
            net.stop()

            # Increment test no.
            test_no += 1

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
            while node["net"] is not None:
                for con in node["net"]:
                    x = 1

                time.sleep(0.5)

        # Buld networks.
        for node in nodes:
            node["net"] = Net(net_type="direct", node_type="passive",
                              passive_port=node["port"], debug=1)
            node["net"].disable_forwarding()
            node["net"].disable_bootstrap()
            node["net"].disable_advertise()
            node["net"].enable_duplicate_ip_cons = 1
            node["net"].start()
            node["thread"] = Thread(target=accept_cons, args=(node,))
            node["thread"].start()

        """
        Make connections.
        Note: duplicate connections will be rejected resulting in just one
        connection from one node to the other nodes.
        """
        for our_node in nodes:
            for their_node in nodes:
                # Don't connect to ourself.
                if our_node == their_node:
                    continue

                # Connect to them.
                our_node["net"].add_node(get_lan_ip(), their_node["port"],
                                         "passive")

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
                assert con.connected
                assert line == "test"

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
        net = Net(debug=1, nat_type="preserving", node_type="simultaneous",
                  net_type="direct", passive_port=10234)
        net.disable_advertise()
        net.disable_bootstrap()
        net.disable_duplicates()
        net.start()
        for i in range(0, 2):
            con = net.add_node(rendezvous_servers[i]["addr"],
                               rendezvous_servers[i]["port"], "passive")
            if con is not None:
                break

        con.set_blocking(1)

        # Test source TCP.
        replies = []
        for i in range(0, max_retransmissions + 1):
            con.send_line("SOURCE TCP")
            print("RESULT = ")
            replies.append(con.recv_line(timeout=5))
            print("RECV LINE replies = ")
            print(con.replies)
            print(con.buf)

        replies = [x for x in replies if x]

        print(replies)
        print(con.buf)
        print(con.replies)
        assert(len(replies) == max_retransmissions)

        # Disable duplicates.
        clear_seen_messages()
        net.enable_duplicates = 1
        con.send_line("SOURCE TCP")
        con.send_line("SOURCE TCP")
        time.sleep(2)
        replies = []
        replies.append(con.recv_line(timeout=5))
        replies.append(con.recv_line(timeout=10))
        replies = [x for x in replies if x]

        print(replies)
        assert(len(replies) == 2)

    def test_00000003(self):
        # Test validate node
        net = Net(debug=1, passive_port=10532)
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
        net = Net(debug=1, nat_type="preserving", node_type="simultaneous",
                  net_type="direct", passive_port=40408)
        net.disable_advertise()
        net.disable_bootstrap()
        net.start()

        # Test passive outbound connection.
        net.add_node(forwarding_servers[0]["addr"],
                     forwarding_servers[0]["port"], "passive")
        assert(len(net.outbound) == 1)
        assert(net.get_connection_no() == 1)

        # 162.218.239.6

        def threaded_add_node(node_ip, node_port, node_type, net, events):
            def add_node(node_ip, node_port, node_type, net, events):
                con = net.add_node(node_ip, node_port, node_type)
                if con is not None:
                    events["success"](con)

            t = Thread(target=add_node,
                       args=(node_ip, node_port, node_type, net, events))
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
            assert 0

        def failure_notify(con):
            assert 0

        def success_notify(con):
            con.close()

        # Test threading hasn't broken the timing.
        events = {
            "failure": failure_notify,
            "success": success_notify
        }

        # NATed VPS: AnRBam11OG1IUEhGVkRKOHQ3cEs4c2dtRMWDYbvALwOowOEG0lc=

        # This is the not-NATed test node.
        net.unl.connect("AlNFMHVDaEVJZ3FnZjl2cXVLcVV1c2dtRMUG79qiBu/aotbFMn4=",
                        events)

        assert(net.validate_node(forwarding_servers[0]["addr"],
                                 forwarding_servers[0]["port"]))

        time.sleep(15)

        net.stop()

    def test_queued_sim_open(self):
        # Test add node.
        net = Net(debug=1, nat_type="preserving", node_type="simultaneous",
                  net_type="direct", passive_port=20283)
        net.disable_advertise()
        net.disable_bootstrap()
        net.start()

        net.unl.connect("AlNFMHVDaEVJZ3FnZjl2cXVLcVV1c2dtRMUG79qiBu/aotbFMn4=",
                        events=None)
        net.unl.connect("AnRBam11OG1IUEhGVkRKOHQ3cEs4c2dtRMWDYbvALwOowOEG0lc=",
                        events=None)
        time.sleep(2)
        assert(len(net.unl.pending_sim_open) == 2)
        net.stop()

    def test_add_duplicate_nodes(self):
        node_1 = Net(
            node_type="passive",
            nat_type="preserving",
            passive_port=0,
            wan_ip="8.8.8.8",
            debug=1
        ).start()

        net = Net(
            net_type="direct",
            node_type="simultaneous",
            nat_type="preserving",
            passive_port=0,
            wan_ip="8.8.8.8",
            debug=1
        ).start()

        con = net.add_node(
            get_lan_ip(),
            node_1.passive_port,
            "passive"
        )
        assert(con is not None)

        print(net.validate_node(
            get_lan_ip(),
            node_1.passive_port
        ))

        node_1.stop()
        net.stop()
