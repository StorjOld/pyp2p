from pyp2p.lib import *
from pyp2p.dht_msg import DHT
from pyp2p.net import Net
import random
from threading import Thread
import time
import logging
from pyp2p.sock import Sock

import random
import os
import tempfile
import hashlib
if sys.version_info >= (3, 0, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse

from pyp2p.unl import UNL


from pyp2p.net import forwarding_servers
net = Net(debug=1, nat_type="preserving", node_type="simultaneous", net_type="direct", passive_port=40408)
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
# NATed node 1:
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


