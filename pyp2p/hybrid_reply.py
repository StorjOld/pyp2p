"""
Defines a reply from the hybrid protocol. Used to add more dynamic routing /
 parsing behaviour for protocol replies.

Recipient:
    source - return reply to connection responsible for sending message that
     resulted in this reply
    everyone - broadcast reply to entire network
    route - open a new connection to one of the routes and send the reply
     to that

Todo: you need to return a special kind of hybrid reply that has a custom
 function that must evaluate to true for the reply to be broadcast.
"""

import time


class HybridReply:
    def __init__(self, msg, network, recipient, retransmit_interval=0,
                 record_seen=1):
        self.msg = msg
        self.network = network
        self.recipient = recipient
        self.source_con = None
        self.routes = []
        self.status_checker = None
        self.last_run_time = time.time()
        self.record_seen = record_seen
        self.retransmit_interval = retransmit_interval
        """
             0 = no retransmit
            -1 = retransmit forever
             n = positive integer that decreases
        """

        def abstract_status_check(hybrid_reply):
            # Reply can be sent or broadcast.
            return 1

            # Reply is not ready to be sent or broadcast.
            return 0

            # Reply is invalid and should be removed from the list.
            return -1

        self.set_status_checker(abstract_status_check)

    def set_status_checker(self, func):
        self.status_checker = func

    def to_str(self):
        s = "%s %s %s %s %s" % (self.network, self.recipient, str(self.routes),
                                str(self.source_con), self.msg)
        return s

    def add_routes(self, routes):
        self.routes = routes

    def copy(self):
        copied_hybrid_reply = HybridReply(self.msg, self.network,
                                          self.recipient)
        copied_hybrid_reply.source_con = self.source_con
        copied_hybrid_reply.routes = self.routes
        return copied_hybrid_reply

if __name__ == "__main__":
    pass
