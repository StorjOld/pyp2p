import requests

try:
    from urllib.parse import urlencode
except:
    from urllib import urlencode

import random

try:
    import json
except:
    import simplejson as json

import binascii

try:
    from Queue import Queue, Full  # py2
except ImportError:
    from queue import Queue, Full  # py3

import time

dht_msg_endpoint = "http://158.69.201.105/pyp2p/dht_msg.php"

class DHTProtocol():
    def __init__(self):
        self.messages_received = Queue(maxsize=100)

class DHT():
    def __init__(self, node_id=None, password=None):
        self.node_id = node_id or self.rand_str(20)
        self.password = password or self.rand_str(30)
        self.check_interval = 3 # For slow connections, unfortunately.
        self.last_check = 0
        self.protocol = DHTProtocol()

        # Register a new "account."
        self.register(self.node_id, self.password)

    def rand_str(self, length):
        return ''.join(random.choice(u'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ') for i in range(length))

    def register(self, node_id, password):
        # Registers a new node to receive messages.
        call = dht_msg_endpoint + "?call=register&"
        call += urlencode({"node_id": node_id}) + "&"
        call += urlencode({"password": password})

        # Make API call.
        response = requests.get(call, timeout=5)

    def put(self, node_id, msg):
        try:
            # Send a message directly to a node in the "DHT"
            call = dht_msg_endpoint + "?call=put&"
            call += urlencode({"node_id": node_id}) + "&"
            call += urlencode({"msg": msg})

            # Make API call.
            response = requests.get(call, timeout=5)
        except:
            pass

    def list(self, node_id, password):
        try:
            # Limit check time to prevent DoSing check server.
            current = time.time()
            if self.last_check:
                elapsed = current - self.last_check
                if elapsed >= self.check_interval:
                    self.last_check = current
                else:
                    return []
            else:
                self.last_check = current

            # Get messages send to us in the "DHT"
            call = dht_msg_endpoint + "?call=list&"
            call += urlencode({"node_id": node_id}) + "&"
            call += urlencode({"password": password})

            # Make API call.
            messages = requests.get(call, timeout=5).text
            messages = json.loads(messages)

            # List.
            if type(messages) == dict:
                messages = [messages]

            # Return a list of responses.
            ret = []
            for msg in messages:
                dht_response = {
                    u"message": msg
                }

                ret.append(dht_response)

            return ret
        except:
            return []

    def direct_message(self, node_id, msg):
        return self.send_direct_message(node_id, msg)

    def send_direct_message(self, node_id, msg):
        if type(node_id) != str:
            node_id = node_id.decode("utf-8")

        self.put(node_id, msg)

    def get_id(self):
        return self.node_id.encode("ascii")

    def has_messages(self):
        for msg in self.list(self.node_id, self.password):
            self.protocol.messages_received.put_nowait(msg)

        return not self.protocol.messages_received.empty()

    def get_messages(self):
        result = []
        while not self.protocol.messages_received.empty():
            result.append(self.protocol.messages_received.get())

        return result


if __name__ == "__main__":
    dht_node = DHT()

    dht_node.send_message(dht_node.node_id, u"sdfsdf")
    dht_node.send_message(dht_node.node_id, b"sdfsdf")
    print(dht_node.node_id)
    print(dht_node.password)
    print(dht_node.list(dht_node.node_id, dht_node.password))