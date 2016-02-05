import logging
import Queue
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
        alice.protocol.messages_received = Queue.Queue()
        bob.protocol.messages_received = Queue.Queue()
        bob.add_relay_link(alice)
        alice.add_relay_link(bob)
        msg = u"test"
        bob.send_direct_message(alice.get_id(), msg)
        assert(alice.has_messages())
        assert(alice.get_messages()[0] == msg)
