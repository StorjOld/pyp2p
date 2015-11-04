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

dht_msg_endpoint = "http://158.69.201.105/pyp2p/dht_msg.php"

class DHT():
    def __init__(self):
        self.node_id = self.rand_str(20)
        self.password = self.rand_str(30)
        self.messages_received = Queue(maxsize=100)

        #Register a new "account."
        self.register(self.node_id, self.password)

    def rand_str(self, length):
        return ''.join(random.choice('0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ') for i in range(length))

    def register(self, node_id, password):
        #Registers a new node to receive messages.
        call  = dht_msg_endpoint + "?call=register&"
        call += urlencode({"node_id": node_id}) + "&"
        call += urlencode({"password": password})

        #Make API call.
        response = requests.get(call)

    def put(self, node_id, msg):
        #Send a message directly to a node in the "DHT"
        call  = dht_msg_endpoint + "?call=put&"
        call += urlencode({"node_id": node_id}) + "&"
        call += urlencode({"msg": msg})

        #Make API call.
        response = requests.get(call)

    def list(self, node_id, password):
        #Get messages send to us in the "DHT"
        call  = dht_msg_endpoint + "?call=list&"
        call += urlencode({"node_id": node_id}) + "&"
        call += urlencode({"password": password})

        #Make API call.
        response = requests.get(call).text
        response = json.loads(response)

        #Return a list of messages.
        return response

    def send_direct_message(self, node_id, msg):
        if type(node_id) != str:
            node_id = node_id.decode("utf-8")

        self.put(node_id, msg)

    def get_id(self):
        return self.node_id.encode("ascii")

    def has_messages(self):
        for msg in self.list(self.node_id, self.password):
            self.messages_received.put_nowait(msg)

        return not self.messages_received.empty()

    def get_messages(self):
        result = []
        while not self.messages_received.empty():
            result.append(self.messages_received.get())

        return result


if __name__ == "__main__":
    dht_node = DHT()

    dht_node.send_message(dht_node.node_id, u"sdfsdf")
    dht_node.send_message(dht_node.node_id, b"sdfsdf")
    print(dht_node.node_id)
    print(dht_node.password)
    print(dht_node.list(dht_node.node_id, dht_node.password))


