"""
Handles P2P connections.
All networking functions are ultimately done through
this class.
"""

import hashlib
import signal
import zlib
from ast import literal_eval

from .nat_pmp import NatPMP
from .rendezvous_client import *
from .unl import UNL
from .upnp import *

# How many times a single message can be retransmitted.
max_retransmissions = 1

# Minimum time that must pass between retransmissions.
min_retransmit_interval = 5

# A theoretical time for a message to propagate across the network.
propagation_delay = 5

# A table of message hashes for received messages.
seen_messages = {}

# How often to get new DHT messages.
dht_msg_interval = 5

# How often to re-bootstrap.
rendezvous_interval = 30 * 60

# How often to re-advertise node.
# Update bootstrapping server every 24 hours.
advertise_interval = 60 * 60 * 12

# Time that must elapse between accepting simultaneous opens.
sim_open_interval = 2

# Bootstrapping + TCP hole punching server.
rendezvous_servers = [
    {
        "addr": "162.243.213.95",
        "port": 8000
    }
]

# Web server running script to test port forwarding.
# And get WAN IP address.
forwarding_servers = [
    {
        "addr": "185.86.149.128",
        "port": 80,
        "url": "/net.php"
    },
    {
        "addr": "185.61.148.22",
        "port": 80,
        "url": "/net.php"
    }
]

# Debug logging.
logging.basicConfig()
log = logging.getLogger(__name__)


def is_msg_old(msg, record_seen=0):
    if type(msg) == str:
        msg = msg.encode("ascii")

    response_hash = hashlib.sha256(msg).hexdigest()
    if response_hash in seen_messages:
        seen = seen_messages[response_hash]
        elapsed = int(time.time()) - seen["last"]
        if elapsed < min_retransmit_interval:
            return 1

        if seen["times"] >= max_retransmissions:
            return 1

    if record_seen:
        record_msg_hash(msg)

    return 0


def record_msg_hash(msg):
    if type(msg) == str:
        msg = msg.encode("ascii")
    response_hash = hashlib.sha256(msg).hexdigest()

    if not is_msg_old(msg):
        timestamp = int(time.time())
        if response_hash in seen_messages:
            seen = seen_messages[response_hash]
            seen["times"] += 1
            seen["last"] = timestamp
        else:
            seen_messages[response_hash] = {
                "times": 1,
                "last": timestamp
            }

        return 1
    else:
        return 0


def clear_seen_messages():
    global seen_messages
    seen_messages = {}


class Net:
    def __init__(self, net_type="p2p", nat_type="unknown", node_type="unknown",
                 max_outbound=10, max_inbound=10, passive_bind="0.0.0.0",
                 passive_port=50500, interface="default", wan_ip=None,
                 dht_node=None, error_log_path="error.log", debug=0,
                 sys_clock=None, servers=None):
        # List of outbound connections (from us, to another node.)
        self.outbound = []

        # List of inbound connections (to us, from another node.)
        self.inbound = []

        # Socket to receive inbound connections on.
        self.passive = None

        # Type of node: simultaneous, active, passive.
        self.node_type = node_type

        # NAT type: preserving, delta, reuse, random.
        self.nat_type = nat_type

        # Address to listen() on for inbound cons.
        self.passive_bind = passive_bind

        # Port to listen() on for inbound cons.
        self.passive_port = int(passive_port)

        # How many connections can we accept from other nodes?
        self.max_outbound = int(max_outbound)

        # How many connections can we make to other nodes?
        self.max_inbound = int(max_inbound)

        # List of servers to do port forwarding checks.
        self.forwarding_servers = forwarding_servers

        # Unix timestamp of last bootstrap.
        self.last_bootstrap = None

        # Unix timestamp of last DHT direct message.
        self.last_dht_msg = None

        # Unix timestamp of last advertise.
        self.last_advertise = None

        # What interface to make outbound connections from?
        self.interface = interface

        # Skip advertise if we have at least this many inbound connections.
        self.min_connected = 3

        # Unix timestamp of last simultaneous open challenge.
        self.last_passive_sim_open = 0

        # Does this Net instance need to bootstrap?
        self.enable_bootstrap = 1

        # Does this Net instance need to advertise?
        self.enable_advertise = 1

        # Should we try open ports?
        self.enable_forwarding = 1

        # Is simultaneous open enabled?
        self.enable_simultaneous = 1

        # Does this Net instance reject duplicate messages
        # (same hash as previous messages)?
        self.enable_duplicates = 1

        # Where should I store errors?
        self.error_log_path = error_log_path

        # Indicates port forwarding state.
        self.forwarding_type = "manual"

        # Debug mode shows debug messages.
        self.debug = debug

        # Network: p2p or direct.
        self.net_type = net_type

        # Calculate clock skew from NTP.
        self.sys_clock = sys_clock

        # List of rendezvous servers.
        self.rendezvous_servers = servers or rendezvous_servers

        # Rendezvous / boostrapping client.
        self.rendezvous = RendezvousClient(
            self.nat_type, rendezvous_servers=self.rendezvous_servers,
            interface=self.interface,
            sys_clock=self.sys_clock
        )

        # DHT node for receiving direct messages from other nodes.
        self.dht_node = dht_node

        # DHT messages received from DHT.
        self.dht_messages = []

        # Subscribes to certain messages from DHT.
        # Todo: move status messages to file transfer client
        def build_dht_msg_handler():
            def dht_msg_handler(node, msg):
                self.debug_print("DHT msg handler in Net")
                valid_needles = [
                    '^REVERSE_CONNECT',
                    '^REVERSE_QUERY',
                    '^REVERSE_ORIGIN',
                    """u?("|')status("|')(:|,)\s+u?("|')SYN("|')""",
                    """u?("|')status("|')(:|,)\s+u?("|')SYN-ACK("|')""",
                    """u?("|')status("|')(:|,)\s+u?("|')ACK("|')""",
                    """u?("|')status("|')(:|,)\s+u?("|')RST("|')""",
                ]

                # Convert zlib packed binary to Python object.
                self.debug_print("In net dht" + str(type(msg)))
                if type(msg) == type(b""):
                    try:
                        msg = literal_eval(zlib.decompress(msg))
                    except:
                        pass

                    # Encode result to unicode for RE checks.
                    """
                    If buffer errors result: enable this.

                    try:
                        if sys.version_info >= (3, 0, 0):
                            if type(msg) == bytes:
                                msg = msg.decode("utf-8")
                        else:
                            if type(msg) == str:
                                msg = unicode(msg)
                    except:
                        return
                    """

                # Check for matches.
                for needle in valid_needles:
                    if re.search(needle, str(msg)) is not None:
                        msg = {
                            u"message": msg,
                            u"source": None
                        }
                        self.dht_messages.append(msg)
                        return

            return dht_msg_handler

        # Add message handler to DHT for our messages.
        self.dht_msg_handler = build_dht_msg_handler()
        if self.dht_node is not None:
            self.dht_node.add_message_handler(self.dht_msg_handler)

        # External IP of this node.
        self.wan_ip = wan_ip or get_wan_ip()

        # Node type details only known after network is start()ed.
        self.unl = None

        # List of connections that still need to respond to
        # our reverse query.
        self.pending_reverse_queries = []

        # Time frame for connection to respond to reverse query.
        self.reverse_query_expiry = 60

        # Enable more than one connection to the same IP.
        self.enable_duplicate_ip_cons = 0

        # Net instances hide their con details to prioritise direct cons.
        if self.net_type == "direct":
            self.disable_bootstrap()
            self.enable_duplicate_ip_cons = 1

        # Set to 1 when self.start() has been called.
        self.is_net_started = 0

        # Start synchronize thread.
        # t = Thread(target=self.synchronize_loop)
        # t.setDaemon(True)
        # t.start()

    def synchronize_loop(self):
        while 1:
            if self.is_net_started:
                self.synchronize()
            time.sleep(5)

    def debug_print(self, msg):
        log.debug(str(msg))

    def disable_duplicates(self):
        self.enable_duplicates = 0

    def disable_bootstrap(self):
        self.enable_bootstrap = 0

    def disable_advertise(self):
        self.enable_advertise = 0

    def disable_simultaneous(self):
        self.enable_simultaneous = 0

    def disable_forwarding(self):
        self.enable_forwarding = 0

    def get_connection_no(self):
        return len(self.outbound) + len(self.inbound)

    # Used to reject duplicate connections.
    def validate_node(self, node_ip, node_port=None, same_nodes=1):
        self.debug_print("Validating: " + node_ip)

        # Is this a valid IP?
        if not is_ip_valid(node_ip) or node_ip == "0.0.0.0":
            self.debug_print("Invalid node ip in validate node")
            return 0

        # Is this a valid port?
        if node_port != 0 and node_port is not None:
            if not is_valid_port(node_port):
                self.debug_print("Invalid node port in validate port")
                return 0

        """
        Don't accept connections from self to passive server
        or connections to already connected nodes.
        """
        if not self.enable_duplicate_ip_cons:
            # Don't connect to ourself.
            if (node_ip == "127.0.0.1" or
                    node_ip == get_lan_ip(self.interface) or
                    node_ip == self.wan_ip):
                self.debug_print("Cannot connect to ourself.")
                return 0

            # No, really: don't connect to ourself.
            if node_ip == self.passive_bind and node_port == self.passive_port:
                self.debug_print("Error connecting to same listen server.")
                return 0

            # Don't connect to same nodes.
            if same_nodes:
                for node in self.outbound + self.inbound:
                    try:
                        addr, port = node["con"].s.getpeername()
                        if node_ip == addr:
                            self.debug_print("Already connected to this node.")
                            return 0
                    except Exception as e:
                        print(e)
                        return 0

        return 1

    # Make an outbound con to a passive or simultaneous node.
    def add_node(self, node_ip, node_port, node_type, timeout=5):
        # Correct type for port.
        node_port = int(node_port)

        # Debug info.
        msg = "Attempting to connect to %s:%s:%s" % (
            node_ip, str(node_port), node_type
        )
        self.debug_print(msg)

        # Already connected to them.
        con = None
        try:
            if not self.enable_duplicate_ip_cons:
                for node in self.outbound + self.inbound:
                    if node_ip == node["ip"]:
                        self.debug_print("Already connected.")
                        con = node["con"]
                        return con

            # Avoid connecting to ourself.
            if not self.validate_node(node_ip, node_port):
                self.debug_print("Validate node failed.")
                return None

            # Make a simultaneous open connection.
            if node_type == "simultaneous" and self.enable_simultaneous:
                # Check they've started net first
                # If they haven't we won't know the NAT details / node type.
                if not self.is_net_started:
                    raise Exception("Make sure to start net before you add"
                                    " node.")

                if self.nat_type in self.rendezvous.predictable_nats:
                    # Attempt to make active simultaneous connection.
                    old_timeout = self.rendezvous.timeout
                    try:
                        self.rendezvous.timeout = timeout
                        self.debug_print("Attempting simultaneous challenge")
                        con = self.rendezvous.simultaneous_challenge(
                            node_ip, node_port, "TCP"
                        )
                    except Exception as e:
                        self.debug_print("sim challenge failed")
                        error = parse_exception(e)
                        self.debug_print(error)
                        log_exception(self.error_log_path, error)
                        return None
                    self.rendezvous.timeout = old_timeout

                    # Record node details and return con.
                    self.rendezvous.simultaneous_cons = []
                    if con is not None:
                        node = {
                            "con": con,
                            "type": "simultaneous",
                            "ip": node_ip,
                            "port": 0
                        }
                        self.outbound.append(node)
                        self.debug_print("SUCCESS")
                    else:
                        self.debug_print("FAILURE")

            # Passive outbound -- easiest to connect to.
            if node_type == "passive":
                try:
                    # Try connect to passive server.
                    con = Sock(node_ip, node_port, blocking=0,
                               timeout=timeout, interface=self.interface)
                    node = {
                        "con": con,
                        "type": "passive",
                        "ip": node_ip,
                        "port": node_port
                    }
                    self.outbound.append(node)
                    self.debug_print("SUCCESS")
                except Exception as e:
                    self.debug_print("FAILURE")
                    error = parse_exception(e)
                    self.debug_print(error)
                    log_exception(self.error_log_path, error)
                    return None

            # Return new connection.
            return con
        finally:
            # Remove undesirable messages from replies.
            # Save message: 0 = no, 1 = yes.
            def filter_msg_check_builder():
                def filter_msg_check(msg):
                    # Allow duplicate replies?
                    record_seen = not self.enable_duplicates

                    # Check if message is old.
                    return not is_msg_old(msg, record_seen)

                return filter_msg_check

            # Patch sock object to reject duplicate replies
            # If it's enabled.
            if con is not None:
                con.reply_filter = filter_msg_check_builder()

    def bootstrap(self):
        """
        When the software is first started, it needs to retrieve
        a list of nodes to connect to the network to. This function
        asks the server for N nodes which consists of at least N
        passive nodes and N simultaneous nodes. The simultaneous
        nodes are prioritized if the node_type for the machine
        running this software is simultaneous, with passive nodes
        being used as a fallback. Otherwise, the node exclusively
        uses passive nodes to bootstrap.

        This algorithm is designed to preserve passive node's
        inbound connection slots.
        """
        # Disable bootstrap.
        if not self.enable_bootstrap:
            return None

        # Avoid raping the rendezvous server.
        t = time.time()
        if self.last_bootstrap is not None:
            if t - self.last_bootstrap <= rendezvous_interval:
                self.debug_print("Bootstrapped recently")
                return None
        self.last_bootstrap = t
        self.debug_print("Searching for nodes to connect to.")

        try:
            connection_slots = self.max_outbound - (len(self.outbound))
            if connection_slots > 0:
                # Connect to rendezvous server.
                rendezvous_con = self.rendezvous.server_connect()

                # Retrieve random nodes to bootstrap with.
                rendezvous_con.send_line("BOOTSTRAP " +
                                         str(self.max_outbound * 2))
                choices = rendezvous_con.recv_line(timeout=2)
                if choices == "NODES EMPTY":
                    rendezvous_con.close()
                    self.debug_print("Node list is empty.")
                    return self
                else:
                    self.debug_print("Found node list.")

                # Parse node list.
                choices = re.findall("(?:(p|s)[:]([0-9]+[.][0-9]+[.][0-9]+[.][0-9]+)[:]([0-9]+))+\s?", choices)
                rendezvous_con.s.close()

                # Attempt to make active simultaneous connections.
                passive_nodes = []
                for node in choices:
                    # Out of connection slots.
                    if not connection_slots:
                        break

                    # Add to list of passive nodes.
                    node_type, node_ip, node_port = node
                    self.debug_print(str(node))
                    if node_type == "p":
                        passive_nodes.append(node)

                # Use passive to make up the remaining cons.
                i = 0
                while i < len(passive_nodes) and connection_slots > 0:
                    node_type, node_ip, node_port = passive_nodes[i]
                    con = self.add_node(node_ip, node_port, "passive")
                    if con is not None:
                        connection_slots -= 1
                        self.debug_print("Con successful.")
                    else:
                        self.debug_print("Con failed.")

                    i += 1

        except Exception as e:
            self.debug_print("Unknown error in bootstrap()")
            error = parse_exception(e)
            log_exception(self.error_log_path, error)

        return self

    def advertise(self):
        """
        This function tells the rendezvous server that our node is ready to
        accept connections from other nodes on the P2P network that run the
        bootstrap function. It's only used when net_type == p2p
        """

        # Advertise is disabled.
        if not self.enable_advertise:
            self.debug_print("Advertise is disbled!")
            return None

        # Direct net server is reserved for direct connections only.
        if self.net_type == "direct" and self.node_type == "passive":
            return None

        # Net isn't started!.
        if not self.is_net_started:
            raise Exception("Please call start() before you call advertise()")

        # Avoid raping the rendezvous server with excessive requests.
        t = time.time()
        if self.last_advertise is not None:
            if t - self.last_advertise <= advertise_interval:
                return None

            if len(self.inbound) >= self.min_connected:
                return None

        self.last_advertise = t

        # Tell rendezvous server to list us.
        try:
            # We're a passive node.
            if self.node_type == "passive" and\
                            self.passive_port is not None and\
                            self.enable_advertise:
                self.rendezvous.passive_listen(self.passive_port,
                                               self.max_inbound)

            """
            Simultaneous open is only used as a fail-safe for connections to
            nodes on the direct_net and only direct_net can list itself as
            simultaneous so its safe to leave this enabled.
            """
            if self.node_type == "simultaneous":
                self.rendezvous.simultaneous_listen()
        except Exception as e:
            error = parse_exception(e)
            log_exception(self.error_log_path, error)

        return self

    def determine_node(self):
        """
        Determines the type of node based on a combination of forwarding
        reachability and NAT type.
        """

        # Manually set node_type as simultaneous.
        if self.node_type == "simultaneous":
            if self.nat_type != "unknown":
                return "simultaneous"

        # Get IP of binding interface.
        unspecific_bind = ["0.0.0.0", "127.0.0.1", "localhost"]
        if self.passive_bind in unspecific_bind:
            lan_ip = get_lan_ip(self.interface)
        else:
            lan_ip = self.passive_bind

        # Passive node checks.
        if lan_ip is not None \
                and self.passive_port is not None and self.enable_forwarding:
            self.debug_print("Checking if port is forwarded.")

            # Check port isn't already forwarded.
            if is_port_forwarded(lan_ip, self.passive_port, "TCP",
                                 self.forwarding_servers):
                msg = "Port already forwarded. Skipping NAT traversal."
                self.debug_print(msg)

                self.forwarding_type = "forwarded"
                return "passive"
            else:
                self.debug_print("Port is not already forwarded.")

            # Most routers.
            try:
                self.debug_print("Trying UPnP")

                UPnP(self.interface).forward_port("TCP", self.passive_port,
                                                  lan_ip)

                if is_port_forwarded(lan_ip, self.passive_port, "TCP",
                                     self.forwarding_servers):
                    self.forwarding_type = "UPnP"
                    self.debug_print("Forwarded port with UPnP.")
                else:
                    self.debug_print("UPnP failed to forward port.")

            except Exception as e:
                # Log exception.
                error = parse_exception(e)
                log_exception(self.error_log_path, error)
                self.debug_print("UPnP failed to forward port.")

                # Apple devices.
                try:
                    self.debug_print("Trying NATPMP.")
                    NatPMP(self.interface).forward_port("TCP",
                                                        self.passive_port,
                                                        lan_ip)
                    if is_port_forwarded(lan_ip, self.passive_port, "TCP",
                                         self.forwarding_servers):
                        self.forwarding_type = "NATPMP"
                        self.debug_print("Port forwarded with NATPMP.")
                    else:
                        self.debug_print("Failed to forward port with NATPMP.")
                        self.debug_print("Falling back on TCP hole punching or"
                                         " proxying.")
                except Exception as e:
                    # Log exception
                    error = parse_exception(e)
                    log_exception(self.error_log_path, error)
                    self.debug_print("Failed to forward port with NATPMP.")

            # Check it worked.
            if self.forwarding_type != "manual":
                return "passive"

        # Fail-safe node types.
        if self.nat_type != "unknown":
            return "simultaneous"
        else:
            return "active"

    # Receive inbound connections.
    def start_passive_server(self):
        self.passive = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.passive.bind((self.passive_bind, self.passive_port))
        self.passive.listen(self.max_inbound)

        # Check bound local port.
        if not self.passive_port:
            self.passive_port = self.passive.getsockname()[1]

    def start(self):
        """
        This function determines node and NAT type, saves connectivity details,
        and starts any needed servers to be a part of the network. This is
        usually the first function called after initialising the Net class.
        """

        self.debug_print("Starting networking.")
        self.debug_print("Make sure to iterate over replies if you need"
                         " connection alive management!")

        # Register a cnt + c handler
        signal.signal(signal.SIGINT, self.stop)

        # Save WAN IP.
        self.debug_print("WAN IP = " + str(self.wan_ip))

        # Check rendezvous server is up.
        try:
            rendezvous_con = self.rendezvous.server_connect()
            rendezvous_con.close()
        except:
            raise Exception("Unable to connect to rendezvous server.")

        # Started no matter what
        # since LAN connections are always possible.
        self.start_passive_server()

        # Determine NAT type.
        if self.nat_type == "unknown":
            self.debug_print("Determining NAT type.")
            nat_type = self.rendezvous.determine_nat()
            if nat_type is not None and nat_type != "unknown":
                self.nat_type = nat_type
                self.rendezvous.nat_type = nat_type
                self.debug_print("NAT type = " + nat_type)
            else:
                self.debug_print("Unable to determine NAT type.")

        # Check NAT type if node is simultaneous
        # is manually specified.
        if self.node_type == "simultaneous":
            if self.nat_type not in self.rendezvous.predictable_nats:
                self.debug_print("Manual setting of simultanous specified but"
                                 " ignored since NAT does not support it.")
                self.node_type = "active"
        else:
            # Determine node type.
            self.debug_print("Determining node type.")

            # No checks for manually specifying passive
            # (there probably should be.)
            if self.node_type == "unknown":
                self.node_type = self.determine_node()

        # Prevent P2P nodes from running as simultaneous.
        if self.net_type == "p2p":
            """
            TCP hole punching is reserved specifically for direct networks
            (a net object reserved for receiving direct connections
            -- p2p is for connecting to the main network. The reason for this
            is you can't do multiple TCP hole punches at the same time so
            reserved for direct network where it's most needed.
            """
            if self.node_type == "simultaneous":
                self.debug_print("Simultaneous is not allowed for P2P")
                self.node_type = "active"
                self.disable_simultaneous()

        self.debug_print("Node type = " + self.node_type)

        # Close stray cons from determine_node() tests.
        self.close_cons()

        # Set net started status.
        self.is_net_started = 1

        # Initialise our UNL details.
        self.unl = UNL(
            net=self,
            dht_node=self.dht_node,
            wan_ip=self.wan_ip
        )

        # Nestled calls.
        return self

    def stop(self, signum=None, frame=None):
        self.debug_print("Stopping networking.")

        if self.passive is not None:
            try:
                self.passive.shutdown(1)
            except:
                pass
            self.passive.close()
            self.passive = None

        if self.last_advertise is not None:
            self.rendezvous.leave_fight()

        """
        Just let the threads timeout by themselves.
        Otherwise mutex deadlocks could occur.
        for unl_thread in self.unl.unl_threads:
            unl_thread.exit()
        """

        for con in self:
            con.close()

        if signum is not None:
            raise Exception("Process was interrupted.")

    # Return a connection that matches a remote UNL.
    def con_by_unl(self, unl, cons=None):
        if cons is None:
            cons = self.outbound + self.inbound
        for con in cons:
            if not isinstance(con, Sock):
                con = con["con"]

            if con.unl is not None:
                self.debug_print("CMP")
                self.debug_print(unl)
                self.debug_print(con.unl)
                if unl == con.unl:
                    # Connection not ready.
                    if con.nonce is None and self.net_type == "direct":
                        continue

                    return con
            else:
                self.debug_print("\a")
                self.debug_print("Con UNL is None (in con by unl)")
                self.debug_print(cons)

        return None

    # Return a connection by its IP.
    def con_by_ip(self, ip):
        for node in self.outbound + self.inbound:
            # Used to block UNLs until nonces are received.
            # Otherwise they might try do I/O and ruin their protocols.
            if self.net_type == "direct":
                if node["con"].nonce is None and self.net_type == "direct":
                    continue

            if node["ip"] == ip:
                return node["con"]

        return None

    def generate_con_id(self, nonce, their_wan_ip, our_wan_ip):
        # Convert WAN IPs to bytes.
        if sys.version_info >= (3, 0, 0):
            if type(their_wan_ip) == str:
                their_wan_ip = their_wan_ip.encode("ascii")

                if type(our_wan_ip) == str:
                    our_wan_ip = our_wan_ip.encode("ascii")
        else:
            if type(their_wan_ip) == unicode:
                their_wan_ip = str(their_wan_ip)

            if type(our_wan_ip) == our_wan_ip:
                our_wan_ip = str(our_wan_ip)

        # Hash WAN IPs to make them the same length.
        their_wan_ip = hashlib.sha256(their_wan_ip).hexdigest().encode("ascii")
        our_wan_ip = hashlib.sha256(our_wan_ip).hexdigest().encode("ascii")

        # Derive fingerprint.
        int_their_wan_ip = int(their_wan_ip, 16)
        int_our_wan_ip = int(our_wan_ip, 16)
        if int_our_wan_ip > int_their_wan_ip:
            fingerprint = hashlib.sha256(our_wan_ip + their_wan_ip)
        else:
            # If both are the same the order doesn't matter.
            fingerprint = hashlib.sha256(their_wan_ip + our_wan_ip)
        fingerprint = fingerprint.hexdigest().encode("ascii")

        # Convert nonce to bytes.
        if sys.version_info >= (3, 0, 0):
            if type(nonce) == str:
                nonce = nonce.encode("ascii")
        else:
            if type(nonce) == unicode:
                nonce = str(nonce)

        # Generate con ID.
        con_id = hashlib.sha256(nonce + fingerprint).hexdigest()

        # Convert to unicode.
        if sys.version_info >= (3, 0, 0):
            if type(con_id) == bytes:
                con_id = con_id.decode("utf-8")
        else:
            if type(con_id) == str:
                con_id = unicode(con_id)

        # Return con ID.
        return con_id

    def con_by_id(self, expected_id):
        for node in self.outbound + self.inbound:
            # Nothing to test.
            if node["con"].nonce is None and self.net_type == "direct":
                self.debug_print("Nonce not set")
                continue

            # Generate con_id from con.
            try:
                their_wan_ip, junk = node["con"].s.getpeername()
            except:
                continue
            if is_ip_private(their_wan_ip):
                our_wan_ip = get_lan_ip(self.interface)
            else:
                our_wan_ip = self.wan_ip
            found_id = self.generate_con_id(
                node["con"].nonce,
                their_wan_ip,
                our_wan_ip
            )

            # Check result.
            if found_id == expected_id:
                return node["con"]

        return None

    # Send a message to all currently established connections.
    def broadcast(self, msg, source_con=None):
        for node in self.outbound + self.inbound:
            if node["con"] != source_con:
                node["con"].send_line(msg)

    def close_cons(self):
        # Close all connections.
        for node in self.inbound + self.outbound:
            node["con"].close()

        # Flush client queue for passive server.
        if self.node_type == "passive" and self.passive is not None:
            self.passive.close()
            self.start_passive_server()

        # Start from scratch.
        self.inbound = []
        self.outbound = []

    def synchronize(self):
        # Clean up dead connections.
        for node_list_name in ["self.inbound", "self.outbound"]:
            node_list = eval(node_list_name)[:]
            for node in node_list:
                if not node["con"].connected:
                    self.debug_print("\a")
                    self.debug_print("Removing disconnected: " + str(node))
                    eval(node_list_name).remove(node)

        # Timeout connections that haven't responded to reverse query.
        old_reverse_queries = []
        for reverse_query in self.pending_reverse_queries:
            duration = time.time() - reverse_query["timestamp"]
            if duration >= self.reverse_query_expiry:
                reverse_query["con"].close()
                old_reverse_queries.append(reverse_query)

        # Remove old reverse queries.
        for reverse_query in old_reverse_queries:
            self.pending_reverse_queries.remove(reverse_query)

        # Get connection nonce (for building IDs.)
        if self.net_type == "direct":
            for node in self.inbound + self.outbound:
                if node["con"].nonce is not None:
                    continue

                # Receive nonce part.
                if len(node["con"].nonce_buf) < 64:
                    assert(node["con"].blocking != 1)
                    remaining = 64 - len(node["con"].nonce_buf)
                    nonce_part = node["con"].recv(remaining)
                    if len(nonce_part):
                        node["con"].nonce_buf += nonce_part

                # Set nonce.
                if len(node["con"].nonce_buf) == 64:
                    node["con"].nonce = node["con"].nonce_buf

        # Check for reverse connect requests.
        if self.dht_node is not None and self.net_type == "direct":
            # Don't do this every synch cycle.
            t = time.time()
            skip_dht_check = 0
            if self.last_dht_msg is not None:
                if t - self.last_dht_msg > dht_msg_interval:
                    skip_dht_check = 1

            if not skip_dht_check and len(self.dht_messages):
                processed = []
                for dht_response in self.dht_messages:
                    # Found reverse connect request.
                    msg = str(dht_response["message"])
                    if re.match("^REVERSE_CONNECT:[a-zA-Z0-9+/-=_\s]+:[a-fA-F0-9]{64}$", msg) is not None:
                        # Process message.
                        self.debug_print(str(msg))
                        call, their_unl, nonce = msg.split(":")
                        their_unl = UNL(value=their_unl).deconstruct()
                        our_unl = UNL(value=self.unl.value).deconstruct()
                        node_id = their_unl["node_id"]

                        # Are we already connected.
                        is_connected = False
                        if nonce == "0" * 64:
                            # Use LAN IPs.
                            their_ip = their_unl["wan_ip"]
                            our_ip = our_unl["wan_ip"]
                            if their_ip == our_ip:
                                their_ip = their_unl["lan_ip"]
                                our_ip = our_unl["lan_ip"]

                            # Get con ID.
                            con_id = self.generate_con_id(
                                nonce,
                                their_ip,
                                our_ip
                            )

                            # Find con if it exists.
                            if self.con_by_id(con_id) is not None:
                                is_connected = True
                        else:
                            if self.con_by_unl(their_unl) is not None:
                                is_connected = True

                        # Skip if already connected.
                        if is_connected:
                            processed.append(dht_response)
                            continue

                        # Ask if the source sent it.
                        def success_builder():
                            def success(con):
                                # Indicate status.
                                self.debug_print("Received reverse connect"
                                                 " notice")
                                self.debug_print(nonce)

                                # Did you send this?
                                query = "REVERSE_QUERY:" + self.unl.value
                                self.dht_node.repeat_relay_message(node_id,
                                                                   query)

                                # Record pending query state.
                                query = {
                                    "unl": their_unl["value"],
                                    "con": con,
                                    "timestamp": time.time()
                                }
                                self.pending_reverse_queries.append(query)

                            return success

                        self.debug_print("Attempting to do reverse connect")
                        self.unl.connect(their_unl["value"],
                                         {"success": success_builder()},
                                         nonce=nonce)

                        processed.append(dht_response)

                    # Found reverse query (did you make this?)
                    elif re.match("^REVERSE_QUERY:[a-zA-Z0-9+/-=_\s]+$", msg)\
                            is not None:
                        # Process message.
                        self.debug_print("Received reverse query")
                        call, their_unl = msg.split(":")
                        their_unl = UNL(value=their_unl).deconstruct()
                        node_id = their_unl["node_id"]

                        # Do we know about this?
                        if their_unl["value"] not in \
                                self.unl.pending_reverse_con:
                            self.debug_print(their_unl)
                            self.debug_print(str(self.unl.pending_reverse_con))
                            self.debug_print("oops, we don't know about this"
                                             " reverse query!")
                            processed.append(dht_response)
                            continue
                        else:
                            self.unl.pending_reverse_con.remove(
                                    their_unl["value"])

                        # Send query.
                        query = "REVERSE_ORIGIN:" + self.unl.value
                        self.dht_node.repeat_relay_message(node_id, query)

                        processed.append(dht_response)

                    # Found reverse origin (yes I made this.)
                    elif re.match("^REVERSE_ORIGIN:[a-zA-Z0-9+/-=_\s]+$", msg) \
                            is not None:
                        self.debug_print("Received reverse origin")
                        for reverse_query in self.pending_reverse_queries:
                            pattern = "^REVERSE_ORIGIN:" + reverse_query["unl"]
                            pattern += "$"
                            if re.match(pattern, msg) is not None:
                                self.debug_print("Removing pending reverse"
                                                 " query: success!")
                                self.pending_reverse_queries.remove(
                                        reverse_query)
                                processed.append(dht_response)

                # Remove processed messages.
                for msg in processed:
                    self.debug_print(msg)
                    self.dht_messages.remove(msg)

            self.last_dht_msg = t

        # Accept inbound connections.
        if len(self.inbound) < self.max_inbound:
            # Accept new passive inbound connections.
            if self.passive is not None:
                r, w, e = select.select([self.passive], [], [], 0)
                for s in r:
                    if s == self.passive:
                        # Accept a new con from the listen queue.
                        client, address = self.passive.accept()
                        con = Sock(blocking=0)
                        con.set_sock(client)
                        node_ip, node_port = con.s.getpeername()

                        # Reject duplicate connections.
                        if self.validate_node(node_ip, node_port):
                            try:
                                node = {
                                    "type": "accept",
                                    "con": con,
                                    "ip": con.s.getpeername()[0],
                                    "port": con.s.getpeername()[1],
                                }
                                self.inbound.append(node)
                                self.debug_print(
                                        "Accepted new passive connection: " +
                                        str(node))
                            except:
                                log.debug("con.s.get")
                        else:
                            self.debug_print("Validation failure")
                            con.close()

            # Accept new passive simultaneous connections.
            if self.node_type == "simultaneous":
                """
                This is basically the code that passive simultaneous
                nodes periodically call to parse any responses from the
                Rendezvous Server which should hopefully be new
                requests to initiate hole punching from active
                simultaneous nodes.

                If a challenge comes in, the passive simultaneous
                node accepts the challenge by giving details to the
                server for the challenging node (active simultaneous)
                to complete the simultaneous open.
                """

                # try:
                t = time.time()
                if self.rendezvous.server_con is not None:
                    for reply in self.rendezvous.server_con:
                        # Reconnect.
                        if re.match("^RECONNECT$", reply) is not None:
                            if self.enable_advertise:
                                self.rendezvous.simultaneous_listen()
                            continue

                        # Find any challenges.
                        # CHALLENGE 192.168.0.1 50184 50185 50186 50187 TCP
                        parts = re.findall("^CHALLENGE ([0-9]+[.][0-9]+[.][0-9]+[.][0-9]+) ((?:[0-9]+\s?)+) (TCP|UDP)$", reply)
                        if not len(parts):
                            continue
                        (candidate_ip, candidate_predictions, candidate_proto)\
                            = parts[0]
                        self.debug_print("Found challenge")
                        self.debug_print(parts[0])

                        # Already connected.
                        if not self.validate_node(candidate_ip):
                            self.debug_print("validation failed")
                            continue

                        # Last meeting was too recent.
                        if t - self.last_passive_sim_open < sim_open_interval:
                            continue

                        # Accept challenge.
                        if self.sys_clock is not None:
                            origin_ntp = self.sys_clock.time()
                        else:
                            origin_ntp = get_ntp()
                        if origin_ntp is None:
                            continue
                        msg = "ACCEPT %s %s TCP %s" % (
                            candidate_ip,
                            self.rendezvous.predictions,
                            str(origin_ntp)
                        )
                        ret = self.rendezvous.server_con.send_line(msg)
                        if not ret:
                            continue

                        """
                        Adding threading here doesn't work because Python's
                        fake threads and the act of starting a thread ruins
                        the timing between code synchronisation - especially
                        code running on the same host or in a LAN. Will
                        compensate by reducing the NTP delay to have the
                        meetings occur faster and setting a limit for meetings
                        to occur within the same period.
                        """
                        # Walk to fight and return holes made.
                        self.last_passive_sim_open = t
                        con = self.rendezvous.attend_fight(
                            self.rendezvous.mappings, candidate_ip,
                            candidate_predictions, origin_ntp
                        )
                        if con is not None:
                            try:
                                node = {
                                    "type": "simultaneous",
                                    "con": con,
                                    "ip": con.s.getpeername()[0],
                                    "port": con.s.getpeername()[1],
                                }
                                self.inbound.append(node)
                            except:
                                log.debug(str(e))
                                pass

                        # Create new predictions ready to accept next client.
                        self.rendezvous.simultaneous_cons = []
                        if self.enable_advertise:
                            self.rendezvous.simultaneous_listen()

        # QUIT - remove us from bootstrapping server.
        if len(self.inbound) == self.max_inbound:
            try:
                # Remove advertise.
                self.rendezvous.leave_fight()
            except:
                pass

        # Bootstrap again if needed.
        self.bootstrap()

        # Relist node again if noded.
        self.advertise()

    """
    These functions here make the class behave like a list. The
    list is a collection of connections (inbound) + (outbound.)
    Every iteration also has the bonus of reaping dead connections,
    making new ones (if needed), and accepting connections
    """
    def __len__(self):
        self.synchronize()
        return len(self.inbound) + len(self.outbound)

    def __iter__(self):
        # Process connections.
        self.synchronize()

        # Copy all connections to single buffer.
        cons = []
        for node in self.inbound + self.outbound:
            if node["con"].nonce is None:
                if self.net_type == "direct":
                    continue

            cons.append(node["con"])

        # Return all cons.
        return iter(cons)

if __name__ == "__main__":
    """
    net = Net(debug=1)
    net.disable_bootstrap()
    net.disable_advertise()
    net.disable_forwarding()
    net.start()
    print(net.unl.value)
    print(net.unl.deconstruct(net.unl.value))

    while 1:
        time.sleep(0.5)

    # Test simultaneous open.
    p2p_net = Net(debug=1, nat_type="preserving", node_type="simultaneous")
    p2p_net.start()
    p2p_net.disable_advertise()
    p2p_net.disable_bootstrap()
    # p2p_net.add_node("192.187.97.131", 0, "simultaneous") # Behind NAT

    def success_notify(con):
        print("SUCCESS THREADING.")

    #Test UNL
    events = {
        "success": success_notify
    }

    while 1:
        time.sleep(0.5)

    exit()

    #P2P network example.
    p2p_net = Net(debug=1)
    p2p_net.start()
    p2p_net.bootstrap()
    p2p_net.advertise()

    #Event loop.
    while 1:
        for con in p2p_net:
            for reply in con:
                print(reply)


            Excluses con from broadcast since we got this message from them

            p2p_net.broadcast("Something.", con)

        time.sleep(0.5)

    #Direct network example.
    dht_node = DHT()
    direct_net = Net(dht_node=dht_node, debug=1)
    direct_net.start()

    #Connect to some UNL.
    def success(con):
        con.send_line("Thanks.")

    #Note: this isn't a valid UNL.
    #To get your UNL do: direct_net.unl.value.
    direct_net.unl.connect("Some guys UNL...", {"success": success})
    """
