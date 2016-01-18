from pyp2p.lib import *
from pyp2p.net import Net
from pyp2p.sys_clock import SysClock

if sys.version_info >= (3, 0, 0):
    pass
else:
    pass


success_no = 0
found_con = 0
test_no_1_success = 1


"""
If the test fails the node may actually be down.
"""

net = Net(
    sys_clock=SysClock(),
    net_type="direct",
    node_type="simultaneous",
    nat_type="preserving",
    passive_port=48310
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

net.stop()

if not connected:
    assert 0

