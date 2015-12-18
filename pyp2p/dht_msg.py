import requests
import time
import sys
import binascii
from ast import literal_eval

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

dht_msg_endpoint = "http://185.61.148.22/dht_msg.php"

class DHTProtocol():
    def __init__(self):
        self.messages_received = Queue(maxsize=100)

class DHT():
    def __init__(self, node_id=None, password=None, debug=1, networking=1):
        self.node_id = node_id or self.rand_str(20)
        if sys.version_info >= (3, 0, 0):
            if type(self.node_id) == str:
                self.node_id = self.node_id.encode("ascii")
        else:
            if type(self.node_id) == unicode:
                self.node_id = str(self.node_id)

        self.node_id = binascii.hexlify(self.node_id).decode('utf-8')
        self.password = password or self.rand_str(30)
        self.check_interval = 3 # For slow connections, unfortunately.
        self.last_check = 0
        self.debug = debug
        self.networking = networking
        self.relay_links = {}
        self.protocol = DHTProtocol()

        # Register a new "account."
        if self.networking:
            assert(self.register(self.node_id, self.password))
        self.message_handlers = set()

    def add_relay_link(self, dht):
        node_id = binascii.hexlify(dht.get_id())
        self.relay_links[node_id.decode("utf-8")] = dht

    def debug_print(self, msg):
        if self.debug:
            print(str(msg))

    def add_message_handler(self, handler):
        self.message_handlers.add(handler)

    def rand_str(self, length):
        return ''.join(random.choice(u'0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ') for i in range(length))

    def register(self, node_id, password, no=1):
        # Only retry up to 5 times.
        if no >= 5:
            return 0
        else:
            no += 1

        try:
            # Registers a new node to receive messages.
            call = dht_msg_endpoint + "?call=register&"
            call += urlencode({"node_id": node_id}) + "&"
            call += urlencode({"password": password})

            # Make API call.
            response = requests.get(call, timeout=5)
            return 1
        except Exception as e:
            print(e)
            self.debug_print("Register timed out in DHT msg")
            time.sleep(1)
            self.register(node_id, password, no)

        self.debug_print("DHT REGISTER FAILED")
        return 0

    def build_dht_response(self, msg):
        try:
            str_types = [type(u""), type(b"")]
            if type(msg) in str_types:
                msg = literal_eval(msg)
        except:
            msg = str(msg)

        dht_response = {
            u"message": msg,
            u"source": None
        }

        return dht_response

    def put(self, node_id, msg, no=1):
        self.debug_print("Sim DHT Put " + str(node_id) + ": " + str(msg))
        if node_id in self.relay_links:
            relay_link = self.relay_links[node_id]
            msg = self.build_dht_response(msg)
            print("in relay link put")
            relay_link.protocol.messages_received.put_nowait(msg)
            return

        if no >= 300:
            return
        else:
            no += 1

        try:
            # Send a message directly to a node in the "DHT"
            call = dht_msg_endpoint + "?call=put&"
            call += urlencode({"node_id": node_id}) + "&"
            call += urlencode({"msg": str(msg)})

            # Make API call.
            response = requests.get(call, timeout=5).text
            self.debug_print(response)
            return

        except Exception as e:
            # Reschedule call.
            self.debug_print("DHT PUT TIMED OUT")
            self.debug_print(e)
            time.sleep(1)
            self.debug_print("Rescheduling DHT PUT")
            self.put(node_id, msg, no)

        self.debug_print("PUT FAILED")

    def list(self, node_id=None, password=None):
        if not self.networking:
            return []

        node_id = node_id or self.node_id
        password = password or self.password
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

            # Record DHT list.
            self.debug_print("In sim DHT list")

            # Get messages send to us in the "DHT"
            call = dht_msg_endpoint + "?call=list&"
            call += urlencode({"node_id": node_id}) + "&"
            call += urlencode({"password": password})

            # Make API call.
            messages = requests.get(call, timeout=5).text
            messages = json.loads(messages)
            self.debug_print("DHT MSG: " + str(messages))

            # List.
            if type(messages) == dict:
                messages = [messages]

            # Return a list of responses.
            ret = []
            if type(messages) == list:
                for msg in messages:
                    dht_response = self.build_dht_response(msg)
                    ret.append(dht_response)

            return ret
        except Exception as e:
            self.debug_print("Exception in dht msg list")
            print(e)
            return []

    def direct_message(self, node_id, msg):
        return self.send_direct_message(node_id, msg)

    def relay_message(self, node_id, msg):
        return self.send_direct_message(node_id, msg)

    def async_direct_message(self, node_id, msg):
        return self.send_direct_message(node_id, msg)

    def send_direct_message(self, node_id, msg):
        if sys.version_info >= (3, 0, 0):
            if type(node_id) == bytes:
                node_id = binascii.hexlify(node_id).decode("utf-8")
        else:
            if type(node_id) == str:
                node_id = binascii.hexlify(node_id).decode("utf-8")

        if type(node_id) != str:
            node_id = node_id.decode("utf-8")

        self.put(node_id, msg)

    def get_id(self):
        node_id = self.node_id
        if sys.version_info >= (3, 0, 0):
            if type(node_id) == str:
                node_id = node_id.encode("ascii")
        else:
            if type(node_id) == unicode:
                node_id = str(node_id)

        return binascii.unhexlify(node_id)

    def has_messages(self):
        for msg in self.list(self.node_id, self.password):
            self.protocol.messages_received.put_nowait(msg)

        return not self.protocol.messages_received.empty()

    def get_messages(self):
        result = []
        if self.has_messages():
            while not self.protocol.messages_received.empty():
                result.append(self.protocol.messages_received.get())

            # Run handlers on messages.
            old_handlers = set()
            for received in result:
                for handler in self.message_handlers:
                    expiry = handler(
                        self,
                        received[u"source"],
                        received[u"message"]
                    )

                    if expiry == -1:
                        old_handlers.add(handler)

            # Expire old handlers.
            for handler in old_handlers:
                self.message_handlers.remove(handler)

            return result

        return result


if __name__ == "__main__":
    #dht_node = DHT(node_id=b"\111" * 20, password="svymQQzF1j7FGmYf8fENs4mvRdAX6f")

    dht_node = DHT(node_id=u"T", password="svymQQzF1j7FGmYf8fENs4mvRdAX6f")

    x = [("a", 2), ("b!%--", 2)]
    dht_node.put(dht_node.node_id, x)
    print(dht_node.list(dht_node.node_id, dht_node.password))



    exit()

    print(dht_node.node_id)
    print(dht_node.get_id())
    print(type(dht_node.get_id()))


    dht_node.send_direct_message(dht_node.node_id, u"test")
    print(dht_node.list(dht_node.node_id, dht_node.password))
    exit()



    print(dht_node.node_id)
    print(dht_node.password)
    print(dht_node.list(dht_node.node_id, dht_node.password))