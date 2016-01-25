"""
Universal Node Locator (UNL.) Allows nodes to direct connect
and helps to debug issues in doing so.
"""

import base64
import binascii
import hashlib
import logging
from threading import Thread, Lock

from .lib import *  # FIXME * is evil!

logging.basicConfig()
log = logging.getLogger(__name__)


def is_valid_unl(value):
    try:
        unl = UNL(value=value)
        ret = unl.deconstruct()
    except:
        return 0

    if ret is None:
        return 0
    else:
        return 1


class UNL:
    def __init__(self, net=None, dht_node=None, value=None, wan_ip=None,
                 debug=0):
        self.unl_threads = []
        self.debug = debug
        self.version = 2
        self.net = net
        self.nat_type_lookup = {
            "m": "random",
            "g": "preserving",
            "e": "reuse"
        }

        self.forwarding_type_lookup = {
            "f": "forwarded",
            "m": "manual",
            "U": "UPnP",
            "N": "NATPMP"
        }

        self.node_type_lookup = {
            "p": "passive",
            "a": "active",
            "s": "simultaneous"
        }

        self.wan_ip = wan_ip or get_wan_ip()

        self.dht_node = dht_node
        if value is not None:
            self.value = value
        else:
            self.value = self.construct()

        # Table of in progress UNLs.
        self.pending_unls = []

        # Sim opens are queued to occur sequentially.
        self.pending_sim_open = []

        # Waiting for a reply.
        self.pending_reverse_con = []

        # Simple mutex.
        self.mutex = Lock()

    def debug_print(self, msg):
        log.debug(str(msg))

    def __eq__(self, other):
        # Compare UNLs. Used to check if a UNL is us.
        our_unl = self.deconstruct(self.value)
        their_unl = self.deconstruct(other.value)

        # Different WAN IPs.
        if our_unl["wan_ip"] != their_unl["wan_ip"]:
            return False

        # Different LAN IPs.
        if our_unl["lan_ip"] != their_unl["lan_ip"]:
            return False

        # Different passive ports.
        if our_unl["listen_port"] != their_unl["listen_port"]:
            return False

        # They are the same.
        return True

    # Operator !=
    def __ne__(self, other):
        return not self == other

    def is_master(self, their_unl):
        # Encode our UNL.
        our_unl = self.value
        if sys.version_info >= (3, 0, 0):
            if type(our_unl) == str:
                our_unl = our_unl.encode("ascii")
        else:
            if type(our_unl) == unicode:
                our_unl = str(our_unl)

        # Encode their UNL.
        if sys.version_info >= (3, 0, 0):
            if type(their_unl) == str:
                their_unl = their_unl.encode("ascii")
        else:
            if type(their_unl) == unicode:
                their_unl = str(their_unl)

        int_our_unl = int(binascii.hexlify(our_unl), 16)
        int_their_unl = int(binascii.hexlify(their_unl), 16)
        if int_our_unl == int_their_unl:
            print("=================================")
            print("OUR UNL == THEIR UNL EDGE CASE")
            print(int_our_unl)
            print(our_unl)
            print(int_their_unl)
            print(their_unl)

        if int_our_unl > int_their_unl:
            master = 1
        else:
            master = 0

        return master

    def get_connection(
        self,
        our_unl,
        their_unl,
        master,
        nonce,
        force_master,
        con_id
    ):
        # Attempt to connect.
        for node_type in ["passive", "simultaneous"]:
            # Matches for this node type.
            nodes = []
            if our_unl["node_type"] == node_type:
                nodes.append(our_unl)

            if their_unl["node_type"] == node_type:
                nodes.append(their_unl)

            # Try the next node type.
            if len(nodes):
                # We only want one connection.
                if len(nodes) == 2:
                    if not master:
                        # They will connect to us.
                        nodes.remove(their_unl)
                    else:
                        # We will connect to them.
                        nodes.remove(our_unl)

                # Don't connect to ourself.
                node = nodes[0]
                if node == their_unl:
                    # Make connection.
                    self.debug_print("Attempting to add node.")
                    con = self.net.add_node(
                        their_unl["wan_ip"], their_unl["listen_port"],
                        their_unl["node_type"], timeout=60
                    )

                    # Configure connection.
                    if con is not None:
                        self.debug_print("Con is not none.")
                        con.nonce = nonce
                        if con.connected:
                            # Send nonce.
                            bytes_sent = con.send(nonce, send_all=1)
                            if bytes_sent != 64 or not con.connected:
                                con = None
                            else:
                                # Set UNL for sock.
                                con.unl = their_unl["value"]
                        else:
                            self.debug_print("Con is not connected!")
                            con = None
                        break
                    else:
                        self.debug_print("Add node returned None! \a")
                else:
                    # Tell them to connect to us.
                    if self.dht_node is not None and force_master:
                        con_request = "REVERSE_CONNECT:%s:%s" % (self.value,
                                                                 nonce)
                        node_id = their_unl["node_id"]
                        if int(binascii.hexlify(node_id), 16):
                            self.pending_reverse_con.append(their_unl["value"])
                            self.dht_node.repeat_relay_message(node_id,
                                                               con_request)

                    # They will connect to us.
                    found_con = 0
                    self.debug_print("Waiting for connection")
                    for i in range(0, 60):
                        # Wait for connection.
                        if con_id is None:
                            con = self.net.con_by_ip(their_unl["wan_ip"])
                        else:
                            con = self.net.con_by_id(con_id)

                        # Indicate con was found.
                        if con is not None:
                            if con.connected:
                                # Set UNL for sock.
                                con.unl = their_unl["value"]

                                # Con was found. Break.
                                found_con = 1
                                break
                            else:
                                self.debug_print("Con is not connected!")
                                con = None
                                break

                        time.sleep(1)

                    if found_con:
                        break

        return con

    def connect_handler(self, their_unl, events, force_master, hairpin, nonce):
        # Figure out who should make the connection.
        our_unl = self.value.encode("ascii")
        their_unl = their_unl.encode("ascii")
        master = self.is_master(their_unl)

        """
        Master defines who connects if either side can. It's used to
        eliminate having multiple connections with the same host.
        """
        if force_master:
            master = 1

        # Deconstruct binary UNLs into dicts.
        our_unl = self.deconstruct(our_unl)
        their_unl = self.deconstruct(their_unl)

        if our_unl is None:
            raise Exception("Unable to deconstruct our UNL.")

        if their_unl is None:
            raise Exception("Unable to deconstruct their UNL.")

        # This means the nodes are behind the same router.
        if our_unl["wan_ip"] == their_unl["wan_ip"]:
            # Connect to LAN IP.
            our_unl["wan_ip"] = our_unl["lan_ip"]
            their_unl["wan_ip"] = their_unl["lan_ip"]

            # Already behind NAT so no forwarding needed.
            if hairpin:
                our_unl["node_type"] = "passive"
                their_unl["node_type"] = "passive"

        # Generate con ID.
        if nonce != "0" * 64:
            # Convert nonce to bytes.
            if sys.version_info >= (3, 0, 0):
                if type(nonce) == str:
                    nonce.encode("ascii")
            else:
                if type(nonce) == unicode:
                    nonce = str(nonce)

            # Check nonce length.
            assert(len(nonce) == 64)

            # Create con ID.
            con_id = self.net.generate_con_id(
                nonce,
                our_unl["wan_ip"],
                their_unl["wan_ip"]
            )
        else:
            con_id = None

        # Acquire mutex.
        self.mutex.acquire()

        # Wait for other UNLs to finish.
        end_time = time.time()
        end_time += len(self.pending_unls) * 60
        self.debug_print("Waiting for other unls to finish")
        while their_unl in self.pending_unls and time.time() < end_time:
            # This is an undifferentiated duplicate.
            if events is None:
                self.mutex.release()
                return

            time.sleep(1)

        self.debug_print("Other unl finished")

        is_exception = 0
        try:
            # Wait for any other hole punches to finish.
            if (their_unl["node_type"] == "simultaneous" and
                    our_unl["node_type"] != "passive"):
                self.pending_sim_open.append(their_unl["value"])
                end_time = time.time()
                end_time += len(self.pending_unls) * 60
                self.debug_print("wait for other hole punches to finish")
                while len(self.pending_sim_open) and time.time() < end_time:
                    if self.pending_sim_open[0] == their_unl["value"]:
                        break

                    time.sleep(1)

                self.debug_print("other hole punches finished")

            # Set pending UNL.
            self.pending_unls.append(their_unl)

            # Release mutex.
            self.mutex.release()

            # Get connection.
            con = self.get_connection(
                our_unl,
                their_unl,
                master,
                nonce,
                force_master,
                con_id
            )
        except Exception as e:
            is_exception = 1
            print(e)
            print("EXCEPTION IN UNL.GET_CONNECTION")
            log_exception("error.log", parse_exception(e))
        finally:
            # Release mutex.
            if self.mutex.locked() and is_exception:
                self.mutex.release()

            # Undo pending connect state.
            if their_unl in self.pending_unls:
                self.pending_unls.remove(their_unl)

            # Undo pending sim open.
            if len(self.pending_sim_open):
                if self.pending_sim_open[0] == their_unl["value"]:
                    self.pending_sim_open = self.pending_sim_open[1:]

        # Only execute events if this function was called manually.
        if events is not None:
            # Success.
            if con is not None:
                if "success" in events:
                    events["success"](con)

            # Failure.
            if con is None:
                if "failure" in events:
                    events["failure"](con)

    def connect(self, their_unl, events, force_master=1, hairpin=1,
                nonce="0" * 64):
        """
        A new thread is spawned because many of the connection techniques
        rely on sleep to determine connection outcome or to synchronise hole
        punching techniques. If the sleep is in its own thread it won't
        block main execution.
        """
        parms = (their_unl, events, force_master, hairpin, nonce)
        t = Thread(target=self.connect_handler, args=parms)
        t.start()
        self.unl_threads.append(t)

    def deconstruct(self, unl=None):
        if unl is None:
            unl = self.value

        try:
            if sys.version_info >= (3, 0, 0):
                # for Python 3
                if isinstance(unl, bytes):
                    unl = unl.decode('ascii')  # or  s = str(s)[2:-1]
            else:
                # for Python 2
                if isinstance(unl, str):
                    unl = unicode(unl)

            # Separate checksum.
            value = unl
            unl = base64.b64decode(unl)
            checksum_size = 4
            checksum = unl[-checksum_size:]
            unl = unl[:-checksum_size]

            # Check checksum.
            digest = hashlib.sha256(hashlib.sha256(unl).digest()).digest()
            digest = digest[0:4]
            if checksum != digest:
                raise Exception("Invalid checksum -- UNL is probably corrupt.")

            # Separate the other fields.
            (
                version, node_id, node_type, nat_type, forwarding_type,
                passive_port, wan_ip, lan_ip
            ) = struct.unpack("<B20sBBBHII", unl)

            node_type = chr(node_type)
            node_type = self.node_type_lookup[node_type]
            nat_type = chr(nat_type)
            nat_type = self.nat_type_lookup[nat_type]
            forwarding_type = chr(forwarding_type)
            forwarding_type = self.forwarding_type_lookup[forwarding_type]

            # Will throw exceptions if invalid IPs.
            wan_ip = int2ip(wan_ip)
            lan_ip = int2ip(lan_ip)

            # Check ports.
            if passive_port:
                if not is_valid_port(passive_port):
                    raise Exception("Invalid passive port for UNL.")

            # Return meaningful fields.
            ret = {
                "value": value,
                "version": version,
                "node_id": node_id,
                "node_type": node_type,
                "nat_type": nat_type,
                "forwarding_type": forwarding_type,
                "listen_port": passive_port,
                "wan_ip": wan_ip,
                "lan_ip": lan_ip,
            }

            return ret
        except Exception as e:
            print(e)
            return None

    def construct(self, details={}):
        # Sanity check.
        if self.net is None:
            raise Exception("Missing Net object for UNL.construct")

        # Translate bind address.
        wan_ip = self.wan_ip
        if "wan_ip" in details:
            wan_ip = details["wan_ip"]

        # Lan IP.
        unspecific_bind = ["0.0.0.0", "127.0.0.1", "localhost"]
        if self.net.passive_bind in unspecific_bind:
            lan_ip = get_lan_ip(self.net.interface)
        else:
            lan_ip = self.net.passive_bind
        if "lan_ip" in details:
            lan_ip = details["lan_ip"]

        # Node id.
        node_id = b"\0" if self.dht_node is None else self.dht_node.get_id()
        if "node_id" in details:
            node_id = details["node_id"]

        # Version.
        version = self.version
        if "version" in details:
            version = details["version"]

        # Node type.
        node_type = self.net.node_type
        if "node_type" in details:
            node_type = details["node_type"]

        # Nat type.
        nat_type = self.net.nat_type
        if "nat_type" in details:
            nat_type = details["nat_type"]

        # Forwarding type.
        forwarding_type = self.net.forwarding_type
        if "forwarding_type" in details:
            forwarding_type = details["forwarding_type"]

        # Listen port.
        listen_port = self.net.passive_port
        if "listen_port" in details:
            listen_port = details["listen_port"]

        # Generate UNL.
        unl = struct.pack(
            "<B20sBBBHII",
            version,
            node_id,
            ord(node_type[0]),
            ord(nat_type[-1]),
            ord(forwarding_type[0]),
            listen_port,
            ip2int(wan_ip),
            ip2int(lan_ip),
        )

        # Build checksum and make base64.
        checksum = hashlib.sha256(hashlib.sha256(unl).digest()).digest()
        checksum = checksum[0:4]
        unl = unl + checksum
        unl = base64.b64encode(unl)
        unl = unl.decode("utf-8")

        return unl

if __name__ == "__main__":
    # global direct_net
    # unl = UNL(direct_net)
    # print(unl.construct())

    # print(unl.deconstruct('x'))

    # print(unl.deconstruct(unl.construct()))
    pass
