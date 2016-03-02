import future
import logging
import requests
import binascii
import random
from queue import Queue
from unittest import TestCase
from pyp2p.dht_msg import DHT

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


class TestDHTMsg(TestCase):
    def test_00001(self):
        dht_node = DHT()
        content = u"content"
        dht_node.send_direct_message(dht_node.node_id, content)
        replies = dht_node.list(dht_node.node_id, dht_node.password)
        print(len(replies))
        assert (len(replies) == 1)
        assert (replies[0] == content)

        dht_node.send_direct_message(dht_node.node_id, content)
        replies = dht_node.list(dht_node.node_id, dht_node.password)
        print(replies)

    def test_relay_link(self):
        bob = DHT(networking=0)
        alice = DHT(networking=0)
        alice.protocol.messages_received = Queue()
        bob.protocol.messages_received = Queue()
        bob.add_relay_link(alice)
        alice.add_relay_link(bob)
        msg = u"test"
        bob.send_direct_message(alice.get_id(), msg)
        assert(alice.has_messages())
        assert(alice.get_messages()[0] == msg)

    def test_dht_logic(self):
        # Todo: switch code to test server and update DHT files
        return
        endpoint = "http://localhost/dht_msg.php"

        # Define auth details.
        alice_node_id = binascii.hexlify(os.urandom(15))
        bob_node_id = binascii.hexlify(os.urandom(15))
        paul_node_id = binascii.hexlify(os.urandom(15))

        # dht_msg.php?call=register&node_id=node&password=pass&ip=127.0.0.1&port=1337
        # Alice register.
        alice_reg_call = endpoint + "?call=register&node_id=" + alice_node_id
        alice_reg_call += "&password=p&ip=127.0.0.1&port=1337"
        assert("success" in requests.get(alice_reg_call, timeout=5).text)

        # Bob register.
        bob_reg_call = endpoint + "?call=register&node_id=" + bob_node_id
        bob_reg_call += "&password=p&ip=127.0.0.1&port=1337"
        assert("success" in requests.get(bob_reg_call, timeout=5).text)

        # dht_msg.php?call=get_mutex&node_id=node&password=pass
        # Alice has mutex.
        call = endpoint + "?call=get_mutex&node_id=" + alice_node_id
        call += "&password=p"
        alice_has_mutex = int(requests.get(call, timeout=5).text)

        # Bob has mutex.
        while True:
            call = endpoint + "?call=get_mutex&node_id=" + bob_node_id
            call += "&password=p"
            bob_has_mutex = int(requests.get(call, timeout=5).text)
            if alice_has_mutex != bob_has_mutex:
                break

        #dht_msg.php?call=put&node_id=node&password=pass&dest_node_id=node&msg=test
        # Alice put to bob.
        call = endpoint + "?call=put&node_id=" + alice_node_id
        call += "&password=p&dest_node_id=" + bob_node_id
        call += "&msg=test"
        assert("success" in requests.get(call, timeout=5).text)

        #dht_msg.php?call=list&node_id=node&password=pass
        # Bob list from Alice.
        call = endpoint + "?call=list&node_id=" + bob_node_id
        call += "&password=p"
        assert("test" in requests.get(call, timeout=5).text)

        # Check last alive and find neighbour logic works as expected.
        if alice_has_mutex:
            master_node_id = alice_node_id
            slave_node_id = bob_node_id
        else:
            master_node_id = bob_node_id
            slave_node_id = alice_node_id

        #dht_msg.php?call=find_neighbours&node_id=node&password=pass
        # Master find neighbours -- this should give us slave ID.
        call = endpoint + "?call=find_neighbours&node_id="
        call += master_node_id + "&password=p"
        assert(slave_node_id in requests.get(call, timeout=5).text)
        assert(slave_node_id not in requests.get(call, timeout=5).text)

        #dht_msg.php?call=reservation_expiry&node_id=node&password=pass&dest_node=id
        # Reset the reservation time for the slave node.
        temp = endpoint + "?call=reservation_expiry&node_id="
        temp += master_node_id + "&password=p"
        temp += "&dest_node_id=" + slave_node_id
        assert("success" in requests.get(temp, timeout=5).text)

        # Try get the same neighbours again.
        # This should work since the reservation_expiry was reset.
        time.sleep(1)
        assert(slave_node_id in requests.get(call, timeout=5).text)

        # dht_msg.php?call=register&node_id=node&password=pass&ip=127.0.0.1&port=1337
        # Paul register.
        paul_reg_call = endpoint + "?call=register&node_id=" + paul_node_id
        paul_reg_call += "&password=p&ip=127.0.0.1&port=1337"
        assert("success" in requests.get(paul_reg_call, timeout=5).text)

        # Paul get mutex (so it shows up in find neighbours.
        paul_mutex_call = endpoint + "?call=get_mutex&node_id=" + paul_node_id
        paul_mutex_call += "&password=p"
        paul_has_mutex = int(requests.get(paul_mutex_call, timeout=5).text)
        # Paul is now on top of the stack.

        time.sleep(2)

        #dht_msg.php?call=last_alive&node_id=node&password=pass
        # Now we refresh the slave's last alive to bump to top.
        call = endpoint + "?call=last_alive&node_id=" + slave_node_id
        call += "&password=p"
        assert("success" in requests.get(call, timeout=5).text)

        # Make sure to also reset its reservation expiry.
        assert("success" in requests.get(temp, timeout=5).text)

        # Test whether last alive bumped node to top.
        call = endpoint + "?call=find_neighbours&node_id="
        call += master_node_id + "&password=p"
        assert(slave_node_id in requests.get(call, timeout=5).text)

