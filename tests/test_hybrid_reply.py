from unittest import TestCase
from pyp2p.lib import *
from pyp2p.dht_msg import DHT
from pyp2p.hybrid_reply import HybridReply
import random


class TestHybridReply(TestCase):
    def test_hybrid_reply(self):
        reply = HybridReply(
            "test",
            "p2p",
            "everyone"
        )

        reply.status_checker(reply)
        reply.add_routes(
            "x"
        )
        reply.copy()


