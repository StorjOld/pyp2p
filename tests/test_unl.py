from pyp2p.net import *
from pyp2p.sock import Sock
from unittest import TestCase
from pyp2p.dht_msg import DHT
from pyp2p.unl import UNL, is_valid_unl


success_no = 0
found_con = 0
test_no_1_success = 1


class TestUNL(TestCase):
    def test_is_valid_unl(self):
        alice_direct = Net(
            net_type="direct",
            node_type="passive",
            nat_type="preserving",
            passive_port="34003",
            wan_ip="8.8.8.8",
            debug=1
        ).start()
        unl = UNL(net=alice_direct)
        assert(is_valid_unl(unl.value))
        assert(unl == unl)
        self.assertFalse(unl != unl)

    def test_nonce_synchronization(self):
        # Setup Alice as master.
        alice_dht = DHT()
        alice_direct = Net(
            net_type="direct",
            node_type="passive",
            nat_type="preserving",
            passive_port=0,
            dht_node=alice_dht,
            debug=1
        ).start()

        assert(alice_direct.node_type == "passive")

        # Setup Bob as slave.
        bob_dht = DHT()
        bob_direct = Net(
            net_type="direct",
            node_type="active",
            nat_type="preserving",
            passive_port=0,
            dht_node=bob_dht,
            debug=1
        ).start()
        bob_port = bob_direct.passive_port
        assert bob_port

        assert(bob_direct.node_type == "active")

        # Setup bogus connection on bob.
        first_con = bob_direct.add_node(get_lan_ip(), bob_port, "passive")
        assert(first_con is not None)

        # Accept connections.
        alice_direct.synchronize()

        # Setup connection handlers.
        def success_builder(first_con):
            def success(con):
                global success_no
                success_no += 1
                assert(con != first_con)

            return success

        def failure(con):
            assert 0

        events = {
            "success": success_builder(first_con),
            "failure": failure
        }

        # Tell alice to connect but wait on specific connection.
        nonce = b"something"
        nonce = hashlib.sha256(nonce).hexdigest()
        bob_direct.unl.connect(alice_direct.unl.value, events, nonce=nonce,
                               hairpin=0, force_master=0)
        alice_direct.unl.connect(bob_direct.unl.value, events, nonce=nonce,
                                 hairpin=0, force_master=0)

        # Process connections.
        end_time = time.time() + 5
        while time.time() < end_time:
            for direct in [alice_direct, bob_direct]:
                for con in direct:
                    print(con)
                    for reply in con:
                        print("Reply in con = ")
                        print(reply)

            time.sleep(0.5)

        assert(success_no == 2)

        # Close networking.
        for direct in [alice_direct, bob_direct]:
            direct.stop()

    def test_reverse_connect(self):
        # Setup Alice as master.
        alice_dht = DHT()
        alice_direct = Net(
            net_type="direct",
            node_type="passive",
            nat_type="preserving",
            passive_port="34005",
            dht_node=alice_dht,
            debug=1
        ).start()

        assert(alice_direct.node_type == "passive")

        # Setup Bob as slave.
        bob_dht = DHT()
        bob_direct = Net(
            net_type="direct",
            node_type="active",
            nat_type="preserving",
            passive_port="34009",
            dht_node=bob_dht,
            debug=1
        ).start()

        assert(bob_direct.node_type == "active")

        # Setup connection handlers.
        def success_builder():
            def success(con):
                print("IN SUCCESS HANDLER \a")
                global found_con
                found_con = 1

            return success

        events = {
            "success": success_builder()
        }

        # Make Bob connect back to Alice.
        alice_direct.unl.connect(bob_direct.unl.value, events, hairpin=0)

        # Process connections.
        end_time = time.time() + 15
        while time.time() < end_time:
            for direct in [alice_direct, bob_direct]:
                direct.dht_node.get_messages()
                for con in direct:
                    print(con)
                    for reply in con:
                        print("Reply in con = ")
                        print(reply)

            time.sleep(0.5)

        print("Found con = " + str(found_con))
        assert(found_con == 1)

        assert(len(alice_direct.pending_reverse_queries) == 0)

        # Close networking.
        for direct in [alice_direct, bob_direct]:
            direct.stop()

    def test_00001(self):
        """
force_master: 0, 1
node_type: passive, simultaneous
wan_ip: same, not same

Overwrite:
    Before test: self.net.con_by_ip() == False
    During test: self.net.con_by_ip == True (simulate con)
    self.net.add_node(

    Start with WAN not same and force_master 1
    Then copy paste: change wan_ip same and change expected results
    ^ No need to very force_master for now since it isn't being directly used.

        Expected = who ends up making add_node
        """

        tests = [
            {
                "force_master": 1,
                "us": {
                    "node_type": "passive",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "passive",
                    "wan_ip": "192.168.0.2"
                },
                "expected": "us"
            },
            {
                "force_master": 1,
                "us": {
                    "node_type": "passive",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.2"
                },
                "expected": "them"
            },
            {
                "force_master": 1,
                "us": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "passive",
                    "wan_ip": "192.168.0.2"
                },
                "expected": "us"
            },
            {
                "force_master": 1,
                "us": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.2"
                },
                "expected": "us"
            },

            # Active.
            {
                "force_master": 1,
                "us": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "active",
                    "wan_ip": "192.168.0.2"
                },
                "expected": "them"
            },
            {
                "force_master": 1,
                "us": {
                    "node_type": "active",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.2"
                },
                "expected": "us"
            },
            {
                "force_master": 1,
                "us": {
                    "node_type": "active",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "active",
                    "wan_ip": "192.168.0.2"
                },
                "expected": "any"
            },

            # Same WAN IP.
            # Node type should end up passive for both!
            {
                "force_master": 1,
                "us": {
                    "node_type": "passive",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.1"
                },
                "expected": "us"
            },

            # Force master only comes into play when there's two
            # nodes of the same type. Master = highest IP.
            {
                "force_master": 0,
                "us": {
                    "node_type": "passive",
                    "wan_ip": "192.168.0.1"
                },
                "them": {
                    "node_type": "passive",
                    "wan_ip": "192.168.0.10"
                },
                "expected": "them"
            },
            {
                "force_master": 0,
                "us": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.10"
                },
                "them": {
                    "node_type": "simultaneous",
                    "wan_ip": "192.168.0.1"
                },
                "expected": "us"
            },
        ]

        unl_template = {
            "version": 1,
            "node_id": b"\0",
            "nat_type": "preserving",
            "forwarding_type": "UPnP",
            "lan_ip": get_lan_ip(),
            "timestamp": time.time(),
            "listen_port": 1337,
            "node_type": None,
            "wan_ip": None
        }

        # Monkey patch for sock.send
        def patched_send(self, msg, send_all=0, timeout=5):
            return 64

        # Patch sock.send
        unpatched_send = Sock.send
        Sock.send = patched_send

        test_no = 1
        for test in tests:
            # Create net object (no start or anything.)
            net = Net(net_type="direct", node_type="passive")

            # Construct our UNL.
            our_unl_template = unl_template.copy()
            our_unl_template["node_type"] = test["us"]["node_type"]
            our_unl_template["wan_ip"] = test["us"]["wan_ip"]
            our_unl = UNL(net).construct(our_unl_template)

            # Construct their UNL.
            their_unl_template = unl_template.copy()
            their_unl_template["node_type"] = test["them"]["node_type"]
            their_unl_template["wan_ip"] = test["them"]["wan_ip"]
            their_unl = UNL(net).construct(their_unl_template)

            print()
            print()
            print("Test no: " + str(test_no))
            print(UNL(net).deconstruct(our_unl))
            print(UNL(net).deconstruct(their_unl))

            # Simulate our network setup.
            test_no += 1
            net.unl = UNL(net)
            net.unl.value = our_unl

            # Create add_node to simulate connections.
            if test["expected"] == "us":
                def add_node_hook(node_ip, node_port, node_type, timeout=5):
                    s = Sock()
                    s.connected = 1
                    return s
            else:
                def add_node_hook(node_ip, node_port, node_type, timeout=5):
                    print("Failure 1")
                    global test_no_1_success
                    test_no_1_success = 0
                    s = Sock()
                    s.connected = 1
                    return s

            # Install add_node hook.
            net.add_node = add_node_hook

            # Bypass initial con_by_ip check.
            def bypass_con_by_ip(ip):
                return None
            net.con_by_ip = bypass_con_by_ip

            # Simulate a new UNL connection.
            net.unl.connect(their_unl, None, test["force_master"])

            # Wait for UNL to block (if it needs to.)
            time.sleep(1)

            # Create con_by_ip to return 1 (simulating inbound connection.
            if test["expected"] == "us":
                def inbound_con_by_ip(ip):
                    print("Failure 2")
                    global test_no_1_success
                    test_no_1_success = 0
                    s = Sock()
                    s.connected = 1
                    return s
            else:
                def inbound_con_by_ip(ip):
                    s = Sock()
                    s.connected = 1
                    return s

            # Install hook.
            net.con_by_ip = inbound_con_by_ip

            # Stop net.
            net.stop()

            # Failure.
            if not test_no_1_success:
                assert 0
                break

        # Unpatch sock.send.
        Sock.send = unpatched_send



