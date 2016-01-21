################
Welcome to PyP2P
################

|BuildLink|_ |CoverageLink|_ |BuildLink2|_ |CoverageLink2|_ |LicenseLink|_

.. |BuildLink| image:: https://img.shields.io/travis/Storj/pyp2p/master.svg?label=Build-Master
.. _BuildLink: https://travis-ci.org/Storj/pyp2p

.. |CoverageLink| image:: https://img.shields.io/coveralls/Storj/pyp2p/master.svg?label=Coverage-Master
.. _CoverageLink: https://coveralls.io/r/Storj/pyp2p

.. |BuildLink2| image:: https://img.shields.io/travis/Storj/pyp2p/develop.svg?label=Build-Develop
.. _BuildLink2: https://travis-ci.org/Storj/pyp2p

.. |CoverageLink2| image:: https://img.shields.io/coveralls/Storj/pyp2p/develop.svg?label=Coverage-Develop
.. _CoverageLink2: https://coveralls.io/r/Storj/pyp2p

.. |LicenseLink| image:: https://img.shields.io/badge/license-MIT-blue.svg
.. _LicenseLink: https://raw.githubusercontent.com/Storj/pyp2p

PyP2P is a simplified networking library for building peer-to-peer networks in Python. The library is designed to solve the pain of finding nodes and bypassing NATs so you can focus on writing your application code.

* Automated port forwarding with UPnP and NATPMP
* Support for TCP hole punching / simultaneous open
* Reverse connect (tell a node to connect to you)
* Fail-safe proxying (planned feature)
* Python 2 (tested on 2.7 - experimental) & 3 (tested on 3.3)
* Linux and Windows - yep

============
Code example
============
PyP2P is designed to work with simple non-blocking TCP sockets. To use them, your application must create an infinite loop which is used to periodically look for new replies. As you look for replies, the software also handles accepting new connections and removing old ones automatically.

The library also handles constructing replies, which are returned in full as a simple list. The underlying message format is a simple line-based protocol: the messages you want to send are terminated with a new line and are returned in full when they've arrived which makes debugging and developing p2p protocols very simple (text-based protocols are easy to debug.)

==========
Alice node
==========
This will create a new listening server on port 44444, bound to listen for connections from the LAN. The interface is specified mostly to ensure that connections are only made from that interface. By default, connections will be made from the default interface (usually wlan0 or eth0) which isn't useful for simulating and testing a P2P network on the same computer.

.. code:: python

    from pyp2p.net import *
    import time

    #Setup Alice's p2p node.
    alice = Net(passive_bind="192.168.0.45", passive_port=44444, interface="eth0:2", node_type="passive", debug=1)
    alice.start()
    alice.bootstrap()
    alice.advertise()

    #Event loop.
    while 1:
        for con in alice:
            for reply in con:
                print(reply)

        time.sleep(1)

========
Bob node
========
This code will make a connection to the Alice node and repeatedly send her the word test. Note how they're both on different interfaces, with completely different IPs. This is necessary for connecting to nodes on the same computer as the library doesn't allow the Net class to connect to itself itself when running in P2P mode (type="p2p" for the Net class.) If you want to be able to make duplicate connections to nodes on the same interface then specify the type as "direct" which will make testing code easier. Note that type is "p2p" by default.

.. code:: python

    from pyp2p.net import *

    #Setup Bob's p2p node.
    bob = Net(passive_bind="192.168.0.44", passive_port=44445, interface="eth0:1", node_type="passive", debug=1)
    bob.start()
    bob.bootstrap()
    bob.advertise()

    #Event loop.
    while 1:
        for con in bob:
            con.send_line("test")

        time.sleep(1)

==============
Direct connect
==============
The code shown so far is good for standard broadcast / flooding style P2P networks where the only requirement is to get a message out to the whole network (e.g. Bitcoin and Bitmessage) - but if you want to do anything more complicated you're going to need to be able to communicate with nodes directly.

Theoretically you can specify the recipient of a message and broadcast it to the network to reach them but this approach won't scale well for most people. What is needed is a way to direct connect to a node with a high level of reliability. To support this function we use something called a UNL: short for Universal Node Locator.

UNLs describe how to connect to a node behind a NAT, firewall, or on the same LAN by looking at the nodes network information in relation to other nodes and using a variety of subversive techniques including UPnP, NATPMP, and TCP hole punching. To further increase the reliability of this code: the software can also be used with a patched instance of the Kademlia DHT to accept direct messages from other nodes on the DHT that instruct it where to connect back to. This is extremely useful for connecting to nodes behind a NAT as it completely bypasses the need for port forwarding assuming that the source is accessible.

.. code:: python

    from pyp2p.net import *
    from pyp2p.unl import UNL
    from pyp2p.dht_msg import DHT
    import time


    #Start Alice's direct server.
    alice_dht = DHT()
    alice_direct = Net(passive_bind="192.168.0.45", passive_port=44444, interface="eth0:2", net_type="direct", dht_node=alice_dht, debug=1)
    alice_direct.start()

    #Start Bob's direct server.
    bob_dht = DHT()
    bob_direct = Net(passive_bind="192.168.0.44", passive_port=44445, interface="eth0:1", net_type="direct", node_type="active", dht_node=bob_dht, debug=1)
    bob_direct.start()

    #Callbacks.
    def success(con):
        print("Alice successfully connected to Bob.")
        con.send_line("Sup Bob.")

    def failure(con):
    print("Alice failed to connec to Bob\a")

    events = {
        "success": success,
        "failure": failure
    }

    #Have Alice connect to Bob.
    alice_direct.unl.connect(bob_direct.unl.construct(), events)

    #Event loop.
    while 1:
    #Bob get reply.
    for con in bob_direct:
        for reply in con:
            print(reply)

    #Alice accept con.
    for con in alice_direct:
        x = 1

    time.sleep(0.5)


In the previous code the Net class was used to spawn a server to accept connections from nodes on the p2p network and managing connections for the purpose of broadcasting. To manage direct connections the same class is used, the difference is the class disables bootstrapping and advertising the connection details to the bootstrapping server as this service is reserved specifically for receiving direct connections.

============
Dependencies
============
* netifaces
* ntplib
* twisted
* ipaddress
* requests
* nose
* setuptools
* pyroute2

Installation: python3.3 setup.py install

Status: Experimental, may have bugs
