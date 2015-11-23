from unittest import TestCase
from pyp2p.lib import *
from pyp2p.dht_msg import DHT
import random


class test_dht_msg(TestCase):
    def test_00001(self):
        dht_node = DHT()
        content = u"content"
        dht_node.send_direct_message(dht_node.node_id, content)
        replies = dht_node.list(dht_node.node_id, dht_node.password)
        print(len(replies))

        assert (len(replies) == 1)
        assert (replies[0]["message"] == content)
        if sys.version_info >= (3, 0, 0):
            assert (type(replies[0]["message"]) == str)
        else:
            assert (type(replies[0]["message"]) == unicode)

        dht_node.send_direct_message(dht_node.node_id, content)
        replies = dht_node.list(dht_node.node_id, dht_node.password)
        print(replies)
        assert (not len(replies))

