from pyp2p.net import *
import time

direct_net = Net(node_type="simultaneous", debug=1)
direct_net.start()
direct_net.disable_bootstrap()
direct_net.advertise()

while 1:
    for con in direct_net:
        for reply in con:
            print(reply)
        x = 1

    time.sleep(0.5)
