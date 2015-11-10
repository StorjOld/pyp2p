from pyp2p.lib import *
from pyp2p.dht_msg import DHT
from pyp2p.net import Net, log
import random
from threading import Thread
import time
import logging
from pyp2p.sock import Sock

# Test add node.
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


exit()



x = Sock()
print(x.blocking)
print()

# Update timeout.
if x.blocking and timeout != None:
    x.set_blocking(1, timeout)

# Check socket is in correct blocking mode.
blocking = x.s.gettimeout()
print(blocking)

exit()
print(blocking)
if x.blocking:
    assert(blocking >= 1 or blocking == None)
else:
    assert(blocking == 0.0)

