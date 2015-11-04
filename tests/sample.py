from pyp2p.lib import *
from pyp2p.dht_msg import DHT
from pyp2p.net import *
import random
from threading import Thread
import time


#Test add node.
net = Net(debug=1, nat_type="preserving", node_type="simultaneous", net_type="direct")
net.disable_advertise()
net.disable_bootstrap()
net.start()

#Test passive outbound connection.
net.add_node(forwarding_servers[0]["addr"], forwarding_servers[0]["port"], "passive")
assert(len(net.outbound) == 1)
assert(net.get_connection_no() == 1)
cons = []
for con in net:
    cons.append(con)
assert(len(cons))

#  162.218.239.6

def threaded_add_node(node_ip, node_port, node_type, net, events):
    def add_node(node_ip, node_port, node_type, events):
        con = net.add_node(node_ip, node_port, node_type)
        if con != None:
            events["success"](con)

    Thread(target=add_node, args=(node_ip, node_port, node_type, net, events))

cons = []
def success_wrapper(cons):
    def success(con):
        cons.append(con)

    return success

events = {
    "success": success_wrapper(cons)
}

net.add_node("192.187.97.131", 0, "simultaneous")


exit()

#Test active simultaneous connection.
#NAT punching node 1:
timeout = time.time() + 10
threaded_add_node("192.187.97.131", 0, "simultaneous", net, events)
while not len(cons) and time.time() < timeout:
    time.sleep(1)

if not len(cons):
    threaded_add_node("162.218.239.6", 0, "simultaneous", net, events)

    while not len(cons) and time.time() < timeout:
        time.sleep(1)
        assert(0)

if len(cons):
    for con in cons:
        con.close()

#Test threading hasn't broken the timing.
events = {
    "failure": failure_notify,
    "success": success_notify
}

#This is the not-NATed test node.
net.unl.connect("AQAAAAAAAAAAAAAAAAAAAAAAAAAAc2dtRMUG79qiBu/aos6tMVYAAAAAWMYQkz0OjrI=", events)

assert(net.validate_node(forwarding_servers[0]["addr"], forwarding_servers[0]["port"]))

net.stop()