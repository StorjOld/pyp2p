from unittest import TestCase
from pyp2p.lib import *
from pyp2p.dht_msg import DHT
from pyp2p.net import *
from pyp2p.unl import UNL


class test_unl(TestCase):
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

            #Same WAN IP.
            #Node type should end up passive for both!
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

            #Force master only comes into play when there's two
            #nodes of the same type. Master = highest IP.
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


        for test in tests:
            #Create net object (no start or anything.)
            net = Net(net_type="direct", node_type="passive")

            #Construct our UNL.
            our_unl_template = unl_template.copy()
            our_unl_template["node_type"] = test["us"]["node_type"]
            our_unl_template["wan_ip"] = test["us"]["wan_ip"]
            our_unl = UNL(net).construct(our_unl_template)

            #Construct their UNL.
            their_unl_template = unl_template.copy()
            their_unl_template["node_type"] = test["them"]["node_type"]
            their_unl_template["wan_ip"] = test["them"]["wan_ip"]
            their_unl = UNL(net).construct(their_unl_template)

            print()
            print()
            print(UNL(net).deconstruct(our_unl))
            print(UNL(net).deconstruct(their_unl))

            #Simulate our network setup.
            net.unl = UNL(net)
            net.unl.value = our_unl

            #Create add_node to simulate connections.
            if test["expected"] == "us":
                def add_node_hook(node_ip, node_port, node_type, timeout=5):
                    assert(1)
                    return 1
            else:
                def add_node_hook(node_ip, node_port, node_type, timeout=5):
                    assert(0)
                    return 1

            #Install add_node hook.
            net.add_node = add_node_hook

            #Bypass initial con_by_ip check.
            def bypass_con_by_ip(ip):
                return None
            net.con_by_ip = bypass_con_by_ip

            #Simulate a new UNL connection.
            net.unl.connect(their_unl, None, test["force_master"])

            #Wait for UNL to block (if it needs to.)
            time.sleep(1)

            #Create con_by_ip to return 1 (simulating inbound connection.
            if test["expected"] == "us":
                def inbound_con_by_ip(ip):
                    assert(0)
                    return 1
            else:
                def inbound_con_by_ip(ip):
                    assert(1)
                    return 1

            #Install hook.
            net.con_by_ip = inbound_con_by_ip


