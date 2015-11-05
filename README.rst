##################
Welcome to PyP2P
##################

PyP2P is a simplified networking library for building peer-to-peer networks in Python. The library is designed to solve the pain of finding nodes and bypassing NATs so you can focus on writing your application code.

* Automated port forwarding with UPnP and NATPMP
* Support for TCP hole punching / simultaneous open
* Reverse connect (tell a node to connect to you)
* Fail-safe proxying (planned feature)
* Python 2 (tested on 2.7 - experimental) & 3 (tested on 3.3)

=============
Code example
=============
PyP2P is designed to work with simple non-blocking TCP sockets. To use them, your application must create an infinite loop which is used to periodically look for new replies. As you look for replies, the software also handles accepting new connections and removing old ones automatically.

The library also handles constructing replies, which are returned in full as a simple list. The underlying message format is a simple line-based protocol: the messages you want to send are terminated with a new line and are returned in full when they've arrived which makes debugging and developing p2p protocols very simple (text-based protocols are easy to debug.)

=============
Alice node
=============
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

============
Bob node
============
This code will make a connection to the Alice node and repeatedly send her the word test. Note how they're both on different interfaces, with completely different IPs. This is necessary as the library doesn't allow the Net class to connect to itself.

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

==============================
Simulating a P2P network
==============================
With pyp2p development its helpful to be able to simulate a p2p network on the same computer to help with testing. To do this, we setup a number of virtual interfaces by editing the */etc/network/interfaces* file. Virtual interfaces help with testing the software by simulating connections from the perspective of other nodes on a LAN which gives them separate IP addresses to the hosting server. Without virtual interfaces the software can't be tested on the same host as the networking class prevents connections from itself to stop bootstrapping problems.

**1. Edit /etc/network/interfaces file.**

.. code:: python

    # The primary network interface
    auto eth0
    iface eth0 inet static
        label eth0
        address 192.168.0.60
        netmask 255.255.255.0
        broadcast 192.168.255
        gateway 192.168.0.1
        dns-servers 8.8.4.4 8.8.8.8
        dns-nameservers 8.8.4.4 8.8.8.8
        up ip addr add 192.168.0.44 brd 192.168.0.255 dev eth0 label eth0:1
        up ip addr add 192.168.0.45 brd 192.168.0.255 dev eth0 label eth0:2

Note that this file will need to match the subnet mask and gateway for your network. To find out what that information is you can type *ifconfig* to view all the interfaces, their IP addresses, and their subnet masks. Use *route -n* to find your gateway address.

**If you're on wireless read this:**

The above instructions assume you're using ethernet to connect to the Internet. Those virtual interfaces aren't going to work if you're using wireless networking. To fix this, you need to somehow bridge wlan0 to eth0, eth0:1, eth0:2, etc, so their packets reach the Internet.

**First: enable NAT.**


.. code:: python

    > sudo echo '1' > /proc/sys/net/ipv4/ip_forward
    > iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE

**Edit /etc/dhcp/dhcpd.conf**

.. code:: python

    subnet 192.168.0.0 netmask 255.255.255.0 {
        range 192.168.0.100 192.168.0.120;
        option routers ip-of-eth0;
        option domain-name-servers the-ip-address-you-have-in-etc-resolv.conf;
    }

The subnet and netmask must match the details chosen for eth0's static configuration in /etc/network/interfaces. The IP address for the routers should match the LAN /static IP of eth0. For domain-name-servers: cat /etc/resolv.conf and use the IP for that. Choose a range that isn't already used for the range (100+ hosts will do) and make sure you use the same network / subnet as eth0.

**Install dhcpd and restart it.**

.. code:: python

    > sudo apt-get install isc-dhcp-server
    > sudo service isc-dhcp-server restart

**2. Disable network-manager for eth0**

Edit /etc/NetworkManager/NetworkManager.conf and ensure the contents looks like this:

.. code:: python

    [ifupdown]
    managed=false

**3. Restart networking.**

.. code:: python

    > sudo su
    > service network-manager stop
    > ifconfig lo up
    > ip addr flush dev eth0
    > ifdown eth0 && ifup -v eth0
    > service network-manager start

**4. Host the bootstrapping server**

P2P networks need a way to find other nodes on the network. The way PyP2P does this is with the rendezvous server (you will have to host this server yourself.)

.. code:: python

    > python3.3 -m "pyp2p.rendezvous_server"

Then edit the rendezvous_server variable at the top of net.py to point to your rendezvous server's IP address.

**5. Host the port forwarding and DHT scripts**

You will also need to host some small PHP scripts that nodes use to check whether their servers can be contacted from the Internet and simulate the actions of a DHT. The scripts are server/net.php and server/dht_msg.php, respectively. The file dht_msg.php requires you edit config.php to point to your database. Import dht_msg.sql into that your database and copy the PHP scripts to a public server. Finally: edit the forwarding_servers variable at the top of net.py and the dht_msg_endpoint variable in dht_msg.py to point to your scripts.

**6. Putting it all together**

.. code:: python

    > Start the bootstrapping server.
    > python3.3 -m "pyp2p.rendezvous_server"
    >
    > Start Alice on one of your virtual interfaces.
    > python3.3 -m "pyp2p.alice"
    >
    > Start Bob on one of your virtual interfaces.
    > python3.3 -m "pyp2p.bob"

=================
Direct connect
=================
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

================
Dependencies
================
* netifaces
* ntplib
* twisted
* ipaddress
* requests
* nose
* setuptools

Installation: python3.3 setup.py install

Status: Experimental, may have bugs
