import sys
import random
import requests
import binascii
import umsgpack
from ast import literal_eval
from future.moves.urllib.parse import urlencode
#from multiprocessing import Process as Thread, Event
from threading import Thread, Event
from storjkademlia.node import Node as KadNode
from pyp2p.lib import is_ip_valid, is_valid_port
from twisted.internet import defer

import json
import string
import binascii

try:
    from Queue import Queue  # py2
except ImportError:
    from queue import Queue  # py3

import time
import logging

dht_msg_endpoint = "http://162.243.213.95/dht_msg.php"
logging.basicConfig()
log = logging.getLogger(__name__)

LONG_POLLING = True
RESERVATION_TIMEOUT = (10 * 60) - 5
MUTEX_TIMEOUT = RESERVATION_TIMEOUT

# Keep up to date so when the reservation timeout has expired
# We're still fairly fresh on the stack.
ALIVE_TIMEOUT = 60 * 5


class DHTProtocol:
    def __init__(self):
        self.messages_received = None


class DHT:
    def __init__(self, node_id=None, ip=None, port=0, password=None, network_id="default", debug=0, networking=1):
        self.node_id = node_id or self.rand_str(20)
        if sys.version_info >= (3, 0, 0):
            if type(self.node_id) == str:
                self.node_id = self.node_id.encode("ascii")
        else:
            if type(self.node_id) == unicode:
                self.node_id = str(self.node_id)

        self.node_id = binascii.hexlify(self.node_id).decode('utf-8')
        self.password = password or self.rand_str(30)
        self.ip = ip
        self.port = port
        self.network_id = network_id
        self.check_interval = 3  # For slow connections, unfortunately.
        self.last_check = 0
        self.debug = debug
        self.networking = networking
        self.relay_links = {}
        self.protocol = DHTProtocol()
        self.is_registered = Event()
        self.is_mutex_ready = Event()
        self.is_neighbours_ready = Event()
        self.handles = []
        self.threads = []
        self.running = 1
        self.has_mutex = 0
        self.neighbours = []

        # Register a new "account."
        if self.networking:
            self.register(self.node_id, self.password)
            self.is_registered.wait(5)
            self.mutex_loop()
            self.is_mutex_ready.wait(5)
            self.alive_loop()
            self.find_neighbours_loop()
            self.is_neighbours_ready.wait(5)
            assert(self.is_mutex_ready.is_set())
            assert(self.is_registered.is_set())

        self.message_handlers = set()

    def stop(self):
        self.running = 0
        for handle in self.handles:
            handle.close()
            # handle.raw._fp.close()

    def hook_queue(self, q):
        self.protocol.messages_received = q
        self.check_for_new_messages()

    def retry_in_thread(self, f, args={"args": None}, check_interval=2):
        def thread_loop(this_obj):
            while 1:
                try:
                    while not f(**args) and this_obj.running:
                        time.sleep(check_interval)

                        if not this_obj.running:
                            return

                    return
                except Exception as e:
                    time.sleep(1)

        t = Thread(target=thread_loop, args=(self,))
        t.setDaemon(True)
        self.threads.append(t)
        t.start()

        return t

    def check_for_new_messages(self):
        def do(args):
            for msg in self.list(self.node_id, self.password):
                self.protocol.messages_received.put(msg)

            return 0

        if LONG_POLLING:
            self.retry_in_thread(do, check_interval=0.1)
        else:
            self.retry_in_thread(do, check_interval=2)

    def mutex_loop(self):
        def do(args):
            # Requests a mutex from the server.
            call = dht_msg_endpoint + "?call=get_mutex&"
            call += urlencode({"node_id": self.node_id}) + "&"
            call += urlencode({"password": self.password})

            # Make API call.
            ret = requests.get(call, timeout=5).text
            if "1" in ret or "0" in ret:
                self.has_mutex = int(ret)
            self.is_mutex_ready.set()

            return 0

        self.retry_in_thread(do, check_interval=MUTEX_TIMEOUT)

    def alive_loop(self):
        def do(args):
            # Requests a mutex from the server.
            call = dht_msg_endpoint + "?call=last_alive&"
            call += urlencode({"node_id": self.node_id}) + "&"
            call += urlencode({"password": self.password})

            # Make API call.
            ret = requests.get(call, timeout=5)

            return 0

        self.retry_in_thread(do, check_interval=ALIVE_TIMEOUT)

    def can_test_knode(self, id):
        for neighbour in self.neighbours:
            if neighbour.id == id:
                if neighbour.can_test:
                    return 1

        return 0

    def has_testable_neighbours(self):
        for neighbour in self.neighbours:
            if neighbour.can_test:
                return 1

        return 0

    def find_neighbours_loop(self):
        def do(args):
            # Requests a mutex from the server.
            call = dht_msg_endpoint + "?call=find_neighbours&"
            call += urlencode({"node_id": self.node_id}) + "&"
            call += urlencode({"password": self.password}) + "&"
            call += urlencode({"network_id": self.network_id})

            # Make API call.
            ret = requests.get(call, timeout=5).text
            ret = json.loads(ret)
            #self.is_neighbours_ready.set()
            #return
            if type(ret) == dict:
                ret = [ret]

            # Convert to kademlia neighbours.
            neighbours = []
            for neighbour in ret:
                if not is_ip_valid(neighbour["ip"]):
                    continue

                neighbour["port"] = int(neighbour["port"])
                if not is_valid_port(neighbour["port"]):
                    continue

                neighbour["can_test"] = int(neighbour["can_test"])
                knode = KadNode(
                    id=binascii.unhexlify(neighbour["id"].encode("ascii")),
                    ip=neighbour["ip"],
                    port=neighbour["port"],
                    can_test=neighbour["can_test"]
                )

                neighbours.append(knode)

            self.neighbours = neighbours
            self.is_neighbours_ready.set()

            return 0

        self.retry_in_thread(do, check_interval=ALIVE_TIMEOUT)

    def get_neighbours(self):
        return self.neighbours

    def add_relay_link(self, dht):
        node_id = binascii.hexlify(dht.get_id())
        self.relay_links[node_id.decode("utf-8")] = dht

    def debug_print(self, msg):
        if self.debug:
            print(str(msg))

    def add_message_handler(self, handler):
        self.message_handlers.add(handler)

    def remove_transfer_request_handler(self, handler):
        pass

    def rand_str(self, length):
        return ''.join(random.choice(string.digits + string.ascii_lowercase +
                                     string.ascii_uppercase
                                     ) for i in range(length))

    def register(self, node_id, password):
        def do(node_id, password):
            try:
                # Registers a new node to receive messages.
                call = dht_msg_endpoint + "?call=register&"
                call += urlencode({"node_id": node_id}) + "&"
                call += urlencode({"password": password}) + "&"
                call += urlencode({"port": self.port}) + "&"
                call += urlencode({"network_id": self.network_id})
                if self.ip is not None:
                   call += "&" + urlencode({"ip": self.ip})

                # Make API call.
                ret = requests.get(call, timeout=5)
                self.handles.append(ret)
                if "success" not in ret.text:
                    return 0
                self.is_registered.set()
                return 1
            except Exception as e:
                self.debug_print("Register timed out in DHT msg")

            self.debug_print("DHT REGISTER FAILED")
            return 0

        mappings = {
            "node_id": node_id,
            "password": password
        }
        self.retry_in_thread(do, mappings)

    def build_dht_response(self, msg):
        msg = binascii.unhexlify(msg)
        msg = umsgpack.unpackb(msg)
        try:
            str_types = [type(u""), type(b"")]
            if type(msg) in str_types:
                msg = literal_eval(msg)
        except:
            msg = str(msg)

        return msg

    def serialize_message(self, msg):
        msg = umsgpack.packb(msg)
        msg = binascii.hexlify(msg)
        return msg

    def async_dht_put(self, key, value):
        d = defer.Deferred()
        def do(args):
            t = self.put(key, value, list_pop=0)
            while t.isAlive():
                time.sleep(1)

            d.callback("success")
            return 1

        self.retry_in_thread(do)
        return d

    def async_dht_get(self, key):
        d = defer.Deferred()
        def do(args):
            ret = self.list(node_id=key, list_pop=0, timeout=5)
            if len(ret):
                d.callback(ret[0])
            else:
                d.callback(None)
            return 1

        self.retry_in_thread(do)
        return d

    def put(self, node_id, msg, list_pop=1):
        def do(node_id, msg):
            if node_id in self.relay_links:
                relay_link = self.relay_links[node_id]
                msg = self.build_dht_response(self.serialize_message(msg))
                relay_link.protocol.messages_received.put_nowait(msg)
                return 1

            try:
                # Send a message directly to a node in the "DHT"
                call = dht_msg_endpoint + "?call=put&"
                call += urlencode({"dest_node_id": node_id}) + "&"
                msg = self.serialize_message(msg)
                call += urlencode({"msg": msg}) + "&"
                call += urlencode({"node_id": self.node_id}) + "&"
                call += urlencode({"password": self.password}) + "&"
                call += urlencode({"list_pop": list_pop})

                # Make API call.
                ret = requests.get(call, timeout=5)
                self.handles.append(ret)
                if "success" not in ret.text:
                    return 0

                return 1

            except Exception as e:
                # Reschedule call.
                self.debug_print("DHT PUT TIMED OUT")
                self.debug_print(e)
                self.debug_print("Rescheduling DHT PUT")

            self.debug_print("PUT FAILED")
            return 0

        mappings = {
            "node_id": node_id,
            "msg": msg
        }
        return self.retry_in_thread(do, mappings)

    def list(self, node_id=None, password=None, list_pop=1, timeout=None):
        if not self.networking:
            return []

        node_id = node_id or self.node_id
        password = password or self.password
        try:
            # Get messages send to us in the "DHT"
            call = dht_msg_endpoint + "?call=list&"
            call += urlencode({"node_id": node_id}) + "&"
            call += urlencode({"password": password}) + "&"
            call += urlencode({"list_pop": list_pop})

            # Make API call.
            if timeout is None:
                if LONG_POLLING:
                    timeout = None
                else:
                    timeout = 4
            ret = requests.get(call, timeout=timeout)
            self.handles.append(ret)
            content_gen = ret.iter_content()
            messages = ret.text
            messages = json.loads(messages)

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
            return []

    def direct_message(self, node_id, msg):
        return self.send_direct_message(node_id, msg)

    def relay_message(self, node_id, msg):
        return self.send_direct_message(node_id, msg)

    def repeat_relay_message(self, node_id, msg):
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
                        received
                    )

                    if expiry == -1:
                        old_handlers.add(handler)

            # Expire old handlers.
            for handler in old_handlers:
                self.message_handlers.remove(handler)

            return result

        return result


if __name__ == "__main__":
    node_1 = DHT(ip="127.0.0.1", port=1337)
    node_2 = DHT(ip="127.0.0.1", port=1338)
    node_3 = DHT(ip="127.0.0.1", port=1339)

    print(node_1.ip)
    print(node_1.port)
    print(node_2.neighbours)

    print("Node 1 has mutex")
    print(node_1.has_mutex)
    print()
    print("Node 2 has mutex")
    print(node_2.has_mutex)
    print()
    print("Node 3 has mutex")
    print(node_3.has_mutex)


    #node1 = DHT()
    #print(node1.get_id())
    #print(node1.node_id)

    pass
    """
    node1 = DHT()
    node2 = DHT()
    node1.put(node2.node_id, "test")
    running = 1
    time.sleep(5)
    node1.stop()
    node2.stop()
    """

    """
    #print(node2.protocol.messages_received.get())
    #print(node2.get_messages())


    while not node2.has_messages() and running:
        for msg in node2.get_messages():
            running = 0
            print(msg)

    print("No longer runnig")
    """


    """
    #dht_node = DHT(node_id=b"\111" * 20, password="svymQQzF1j7FGmYf8fENs4mvRd")

    dht_node = DHT(node_id=u"T", password="svymQQzF1j7FGmYf8fENs4mvRd")

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
    """
