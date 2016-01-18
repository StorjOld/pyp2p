from unittest import TestCase
from pyp2p.hybrid_reply import HybridReply


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
