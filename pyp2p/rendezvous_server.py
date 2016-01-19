"""
The purpose of this server is to maintain a list of
nodes connected to the P2P network. It supports traditional
passive nodes which receive connections but it also
provides a protocol to facilitate TCP hole punching
allowing >85% of nodes behind a standard router to
receive connections.

Notes: Passives nodes don't keep a persistent connection
to the rendezvous server because they don't need to
and it would be unnecessarily taxing. For this reason,
the list of passive nodes retrieved from bootstrapping
may be stale but they are periodically cleaned every node
life time. Additionally, well behaved passive nodes
send the clear command which causes the server to remove
the node details.
"""

from twisted.internet import reactor
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver

from .lib import *

error_log_path = "error.log"
debug = 1


class RendezvousProtocol(LineReceiver):
    def __init__(self, factory):
        self.factory = factory
        self.challege_timeout = 60 * 2  # Seconds.
        self.node_lifetime = 60 * 60 * 24  # 12 hours.
        self.cleanup = 5 * 60  # Every 5 minutes.
        self.max_candidates = 100  # Per simultaneous node.
        self.connected = False

    def log_entry(self, msg, direction="none"):
        if sys.version_info >= (3, 0, 0):
            if type(msg) == bytes:
                msg = msg.decode("utf-8")
        ip_addr = str(self.transport.getPeer().host)
        port = str(self.transport.getPeer().port)
        when = time.strftime("%H:%M:%S %Y-%m-%d")
        who = """%s:%s""" % (ip_addr, port)
        if direction == "send":
            direction = " -> "
        elif direction == "recv":
            direction = " <- "
        else:
            direction = " "

        entry = """[%s] %s%s%s""" % (when, msg, direction, who)
        return entry

    def send_line(self, msg):
        # Not connected.
        if not self.connected:
            return

        # Network byte order.
        try:
            if type(msg) != bytes:
                msg = msg.encode("ascii")
        except Exception as e:
            print("send line e")
            print(e)
            return

        # stdout for debugging.
        if debug:
            print(self.log_entry(msg, "send"))

        self.sendLine(msg)

    def send_remote_port(self):
        """
        Sends the remote port mapped for the connection.
        This port is surprisingly often the same as the locally
        bound port for an endpoint because a lot of NAT types
        preserve the port.
        """
        msg = "REMOTE TCP %s" % (str(self.transport.getPeer().port))
        self.send_line(msg)

    def is_valid_ipv4_address(self, address):
        try:
            socket.inet_pton(socket.AF_INET, address)
        except AttributeError:  # no inet_pton here, sorry
            try:
                socket.inet_aton(address)
            except socket.error:
                return False
            return address.count('.') == 3
        except socket.error:  # not a valid address
            return False

        return True

    def is_valid_port(self, port):
        port = re.findall("^[0-9]+$", str(port))
        if len(port):
            port = int(port[0])
            if 0 < port <= 65535:
                return 1
        return 0

    def cleanup_candidates(self, node_ip):
        """
        Removes old TCP hole punching candidates for a
        designated node if a certain amount of time has passed
        since they last connected.
        """
        if node_ip in self.factory.candidates:
            old_candidates = []
            for candidate in self.factory.candidates[node_ip]:
                elapsed = int(time.time() - candidate["time"])
                if elapsed > self.challege_timeout:
                    old_candidates.append(candidate)

            for candidate in old_candidates:
                self.factory.candidates[node_ip].remove(candidate)

    def propogate_candidates(self, node_ip):
        """
        Used to progate new candidates to passive simultaneous
        nodes.
        """

        if node_ip in self.factory.candidates:
            old_candidates = []
            for candidate in self.factory.candidates[node_ip]:
                # Not connected.
                if not candidate["con"].connected:
                    continue

                # Already sent -- updated when they accept this challenge.
                if candidate["propogated"]:
                    continue

                # Notify node of challege from client.
                msg = "CHALLENGE %s %s %s" % (
                    candidate["ip_addr"],
                    " ".join(map(str, candidate["predictions"])),
                    candidate["proto"])

                self.factory.nodes["simultaneous"][node_ip]["con"].\
                    send_line(msg)
                old_candidates.append(candidate)

    def synchronize_simultaneous(self, node_ip):
        """
        Because adjacent mappings for certain NAT types can
        be stolen by other connections, the purpose of this
        function is to ensure the last connection by a passive
        simultaneous node is recent compared to the time for
        a candidate to increase the chance that the precited
        mappings remain active for the TCP hole punching
        attempt.
        """

        for candidate in self.factory.candidates[node_ip]:
            # Only if candidate is connected.
            if not candidate["con"].connected:
                continue

            # Synchronise simultaneous node.
            if candidate["time"] -\
                    self.factory.nodes["simultaneous"][node_ip]["time"] >\
                    self.challege_timeout:
                msg = "RECONNECT"
                self.factory.nodes["simultaneous"][node_ip]["con"].\
                    send_line(msg)
                return

        self.cleanup_candidates(node_ip)
        self.propogate_candidates(node_ip)

    def connectionMade(self):
        try:
            self.connected = True
            if debug:
                print(self.log_entry("OPENED =", "none"))

            # Force reconnect if node has candidates and the timeout is old.
            ip_addr = self.transport.getPeer().host
            if ip_addr in self.factory.nodes["simultaneous"]:
                # Update time.
                self.factory.nodes["simultaneous"][ip_addr]["time"] =\
                    time.time()
                self.synchronize_simultaneous(ip_addr)
        except Exception as e:
            error = parse_exception(e)
            log_exception(error_log_path, error)
            print(self.log_entry("ERROR =", error))

    def connectionLost(self, reason):
        """
        Mostly handles clean-up of node + candidate structures.
        Avoids memory exhaustion for a large number of connections.
        """
        try:
            self.connected = False
            if debug:
                print(self.log_entry("CLOSED =", "none"))

            # Every five minutes: cleanup
            t = time.time()
            if time.time() - self.factory.last_cleanup >= self.cleanup:
                self.factory.last_cleanup = t

                # Delete old passive nodes.
                old_node_ips = []
                for node_ip in list(self.factory.nodes["passive"]):
                    passive_node = self.factory.nodes["passive"][node_ip]
                    # Gives enough time for passive nodes to receive clients.
                    if t - passive_node["time"] >= self.node_lifetime:
                        old_node_ips.append(node_ip)
                for node_ip in old_node_ips:
                    del self.factory.nodes["passive"][node_ip]

                # Delete old simultaneous nodes.
                old_node_ips = []
                for node_ip in list(self.factory.nodes["simultaneous"]):
                    simultaneous_node =\
                        self.factory.nodes["simultaneous"][node_ip]
                    # Gives enough time for passive nodes to receive clients.
                    if t - simultaneous_node["time"] >= self.node_lifetime:
                        old_node_ips.append(node_ip)
                for node_ip in old_node_ips:
                    del self.factory.nodes["simultaneous"][node_ip]

                # Delete old candidates and candidate structs.
                old_node_ips = []
                for node_ip in list(self.factory.candidates):
                    # Record old candidates.
                    old_candidates = []
                    for candidate in self.factory.candidates[node_ip]:
                        # Hole punching is ms time sensitive.
                        # Candidates older than this is safe to assume
                        # they're not needed.
                        if node_ip not in self.factory.nodes["simultaneous"] \
                                and t - candidate["time"] >= self.challenge_timeout * 5:
                            old_candidates.append(candidate)

                    # Remove old candidates.
                    for candidate in old_candidates:
                        self.factory.candidates[node_ip].remove(candidate)

                    # Record old node IPs.
                    if not len(self.factory.candidates[node_ip]) and \
                            node_ip not in self.factory.nodes["simultaneous"]:
                        old_node_ips.append(node_ip)

                # Remove old node IPs.
                for node_ip in old_node_ips:
                    del self.factory.candidates[node_ip]
        except Exception as e:
            error = parse_exception(e)
            log_exception(error_log_path, error)
            print(self.log_entry("ERROR =", error))

    def lineReceived(self, line):
        # Unicode for text patterns.
        try:
            line = line.decode("utf-8")
        except:
            # Received invalid characters.
            return
        if debug:
            print(self.log_entry(line, "recv"))

        try:
            # Return nodes for bootstrapping.
            if re.match("^BOOTSTRAP", line) is not None:
                parts = re.findall("^BOOTSTRAP ([0-9]+)", line)
                while 1:
                    # Invalid response.
                    if not len(parts):
                        break
                    n = int(parts[0])

                    # Invalid number.
                    if n < 1 or n > 100:
                        break

                    # Bootstrap n passive, n .
                    msg = "NODES "
                    node_types = ["passive"]
                    our_ip = self.transport.getPeer().host
                    node_no = 0
                    for node_type in node_types:
                        ip_addr_list = list(self.factory.nodes[node_type])
                        for i in range(0, n):
                            # There's no nodes left to bootstrap with.
                            ip_addr_list_len = len(ip_addr_list)
                            if not ip_addr_list_len:
                                break

                            # Choose a random node.
                            rand_index = random.randrange(0, ip_addr_list_len)
                            ip_addr = ip_addr_list[rand_index]
                            element = self.factory.nodes[node_type][ip_addr]

                            # Skip our own IP.
                            if our_ip == ip_addr or ip_addr == "127.0.0.1":
                                i -= 1
                                ip_addr_list.remove(ip_addr)
                                continue

                            # Not connected.
                            if node_type == "simultaneous" and\
                                    not element["con"].connected:
                                i -= 1
                                ip_addr_list.remove(ip_addr)
                                continue

                            # Append new node.
                            msg += node_type[0] + ":" + ip_addr + ":"
                            msg += str(element["port"]) + " "
                            ip_addr_list.remove(ip_addr)
                            node_no += 1

                    # No nodes in response.
                    if not node_no:
                        msg = "NODES EMPTY"

                    # Send nodes list.
                    self.send_line(msg)
                    break

            # Add node details to relevant sections.
            if re.match("^(SIMULTANEOUS|PASSIVE) READY [0-9]+ [0-9]+$", line)\
                    is not None:
                # Get type.
                node_type, passive_port, max_inbound = re.findall("^(SIMULTANEOUS|PASSIVE) READY ([0-9]+) ([0-9]+)", line)[0]
                node_type = node_type.lower()
                valid_node_types = ["simultaneous", "passive"]
                if node_type not in valid_node_types:
                    return

                # Init / setup.
                node_ip = self.transport.getPeer().host
                self.factory.nodes[node_type][node_ip] = {
                    "max_inbound": max_inbound,
                    "no": 0,
                    "port": passive_port,
                    "time": time.time(),
                    "con": self,
                    "ip_list": []
                }

                # Passive doesn't have a candidates list.
                if node_type == "simultaneous":
                    if node_ip not in self.factory.candidates:
                        self.factory.candidates[node_ip] = []
                    else:
                        self.cleanup_candidates(node_ip)
                        self.propogate_candidates(node_ip)

            # Echo back mapped port.
            if re.match("^SOURCE TCP", line) is not None:
                self.send_remote_port()

            # Client wishes to actively initate a simultaneous open.
            if re.match("^CANDIDATE", line) is not None:
                # CANDIDATE 192.168.0.1 TCP.
                parts = re.findall("^CANDIDATE ([0-9]+[.][0-9]+[.][0-9]+[.][0-9]+) (TCP|UDP) ((?:[0-9]+\s?)+)$", line)
                while 1:
                    # Invalid response.
                    if not len(parts):
                        break
                    node_ip, proto, predictions = parts[0]
                    predictions = predictions.split(" ")
                    client_ip = self.transport.getPeer().host

                    # Invalid IP address.
                    if not self.is_valid_ipv4_address(node_ip):
                        print("Candidate invalid ip4" + str(node_ip))
                        break
                    if node_ip not in self.factory.nodes["simultaneous"]:
                        print("Candidate: node ip not in factory nodes sim.")
                        break

                    # Valid port.
                    valid_ports = 1
                    for port in predictions:
                        if not self.is_valid_port(port):
                            valid_ports = 0
                    if not valid_ports:
                        print("Candidate not valid port")
                        break

                    # Not connected.
                    if not self.factory.nodes["simultaneous"][node_ip]["con"].\
                            connected:
                        print("Candidate not connected.")
                        break

                    candidate = {
                        "ip_addr": client_ip,
                        "time": time.time(),
                        "predictions": predictions,
                        "proto": proto,
                        "con": self,
                        "propogated": 0
                    }

                    # Delete candidate if it already exists.
                    if node_ip in self.factory.candidates:
                        # Max candidates reached.
                        num_candidates = len(self.factory.candidates[node_ip])
                        if num_candidates >= self.max_candidates:
                            print("Candidate max candidates reached.")
                            break

                        for test_candidate in self.factory.candidates[node_ip]:
                            if test_candidate["ip_addr"] == client_ip:
                                self.factory.candidates[node_ip].remove(test_candidate)
                                print("Candidate removign test canadidate.")
                                break

                    self.factory.candidates[node_ip].append(candidate)
                    candidate_index = len(self.factory.candidates[node_ip]) - 1

                    # Update predictions.
                    self.factory.candidates[node_ip][candidate_index]["predictions"] = predictions
                    msg = "PREDICTION SET"
                    self.send_line(msg)

                    # Synchronize simultaneous node.
                    self.synchronize_simultaneous(node_ip)
                    break

            # Node wishes to respond to a simultaneous open challenge from
            # a client.
            if re.match("^ACCEPT", line) is not None:
                # ACCEPT 192.168.0.1 4552 345 TCP 1412137849.288068
                p = "^ACCEPT ([0-9]+[.][0-9]+[.][0-9]+[.][0-9]+)"
                p += " ((?:[0-9]+\s?)+) (TCP|UDP) ([0-9]+(?:[.][0-9]+)?)$"
                parts = re.findall(p, line)
                while 1:
                    # Invalid reply.
                    if not len(parts):
                        break
                    client_ip, predictions, proto, ntp = parts[0]

                    # Invalid IP address.
                    node_ip = self.transport.getPeer().host
                    if node_ip not in self.factory.candidates:
                        break

                    # Invalid predictions.
                    predictions = predictions.split(" ")
                    valid_ports = 1
                    for port in predictions:
                        if not self.is_valid_port(port):
                            valid_ports = 0
                    if not valid_ports:
                        break

                    # Invalid NTP.
                    ntp = ntp
                    t = time.time()
                    minute = 60 * 10
                    if int(float(ntp)) < t - minute or\
                            int(float(ntp)) > t + minute:
                        break

                    # Relay fight to client_ip.
                    # FIGHT 192.168.0.1 4552 345 34235 TCP 123123123.1
                    msg = "FIGHT %s %s %s %s" % (node_ip, " ".join(map(str, predictions)), proto, str(ntp))
                    for candidate in self.factory.candidates[node_ip]:
                        if candidate["ip_addr"] == client_ip:
                            candidate["con"].send_line(msg)

                            """
                            Signal to propogate_candidates() not to relay this
                            candidate again. Note that this occurs after a
                            valid accept which thus counts as acknowledging
                            receiving the challenge.
                            """
                            candidate["propogated"] = 1
                            break

                    break

            # Remove node details.
            if re.match("^CLEAR", line) is not None:
                ip_addr = self.transport.getPeer().host
                if ip_addr in self.factory.nodes["passive"]:
                    del self.factory.nodes["passive"][ip_addr]
                if ip_addr in self.factory.nodes["simultaneous"]:
                    del self.factory.nodes["simultaneous"][ip_addr]

            # Disconnect.
            if re.match("^QUIT", line) is not None:
                self.transport.loseConnection()

        except Exception as e:
            error = parse_exception(e)
            log_exception(error_log_path, error)
            print(self.log_entry("ERROR =", error))


class RendezvousFactory(Factory):
    """
    PASSIVE
    A node with the incoming port successfully reachable.
    For clients, this is done by opening the port.

    Outbound: Passive, simultaneous
    Inbound: Active, passive, simultaneous

    SIMULTANEOUS
    This is a node with a predictable NAT. TCP hole
    punching can be used to connect to these nodes.
    Note that a simultaneous node can technically
    also be a passive node and may be added to
    both categories.

    Outbound: Passive, simultaneous
    Inbound: Active, passive, simultaneous

    ACTIVE
    (For explanation only, this struct isn't used.)

    Active nodes are nodes which can only make outgoing
    connections - they cannot receive any. These nodes are
    problematic in a P2P network because a P2P network by
    definition requires nodes capable of receiving connections,
    or incoming connections to form the network. As a
    network first starts, it's likely there will be a lot
    more active nodes than anything else which will tax the
    network by taking up those limited inbound connection slots.
    Simultaneous nodes were created to try solve this problem
    and greatly make bootstrapping more automagic and user-friendly.

    Outbound: Passive, simultaneous
    Inbound:

    RELAY
    Not yet used: Relay nodes will be nodes capable of
    relaying connections on behalf of other nodes.

    BOOTSTRAP
    Not yet used: A list of other servers which can be
    used for bootstrapping.
    """

    def __init__(self):
        self.last_cleanup = time.time()
        self.candidates = {}
        self.nodes = {
            'passive': {},
            'simultaneous': {},
            'active': {},
            'relay': {},
            'bootstrap': {}
        }

        # Test data.
        """
        test_ip = "192.168.0.10"
        self.nodes["passive"][test_ip] = {
            "ip_addr": test_ip,
            "port": 194,
        }
        self.nodes["simultaneous"][test_ip] = {
            "time": time.time(),
            "ip_addr": test_ip,
            "port": 0
        }
        self.candidates[test_ip] = []
        """

    def buildProtocol(self, addr):
        return RendezvousProtocol(self)

if __name__ == "__main__":
    print("Starting rendezvous server.")
    factory = RendezvousFactory()
    reactor.listenTCP(8000, factory, interface="0.0.0.0")
    reactor.run()

