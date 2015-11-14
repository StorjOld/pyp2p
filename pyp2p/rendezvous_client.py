"""
This module handles all the operations required to bootstrap
the peer-to-peer network. It includes a custom client for
talking to the Rendezvous Server allowing the program to
accept and request connections with simultaneous and passive
nodes.

* A passive node is a node which can receive inbound connections.
* A simultaneous node is a node that cannot receive inbound
connections but its NAT uses predictable mapping so it can
receive connections through TCP hole punching.
    * A simultaneous node seeking to initiate hole punching I
    refer to as an "active simultaneous node."
    * A simultaneous node which has already bootstrapped
    becomes a "passive simultaneous node" whose purpose it
    is to accept challenges from active simultaneous nodes
    until its inbound slots are full.
* All other nodes are active nodes. Leechers who can only make
connections and take up valuable slots in the network.

The only special thing about this module is the TCP hole
punching algorithm, also known as TCP simultaneous open - it
works by timing two connections to occur simultaneously so that
their SYN 3-way handshakes cross over in such a way that their
TCP state machines consider the connection open. To do this,
you predict the NAT's remote mapping for the port and arrange
for both nodes to connect to each other's predicted port
simultaneously.

Todo: 
* Add better exception handling and tests. 
"""

import socket
import re
import os
import sys
import ntplib
import datetime
import random
from multiprocessing.dummy import Pool

from .sock import *
from .lib import *

class RendezvousClient:
    def __init__(self, nat_type, rendezvous_servers, interface="default"):
        self.nat_type = nat_type
        self.delta = 0
        self.port_collisions = 1
        self.nat_tests = 5
        self.server_con = None
        self.mappings = None
        self.predictions = None
        self.simultaneous_cons = []
        self.ntp = 0
        self.mapping_no = 4
        self.rendezvous_servers = rendezvous_servers
        self.interface = interface
        self.ntp_delay = 6
        self.timeout = 5 # Socket timeout.
        self.predictable_nats = ["preserving", "delta"]

    def server_connect(self, sock=None):
        for server in self.rendezvous_servers:
            try:
                # Blank socket object.
                con = Sock(
                    blocking=1,
                    interface=self.interface,
                    timeout=2
                )

                # Pre-bound socket.
                if sock != None:
                    con.set_sock(sock)

                # Connect the socket.
                con.connect(server["addr"], server["port"])

                # Return Sock object.
                return con
            except:
                continue

        raise Exception("All rendezvous servers are down.")

    # Delete any old rendezvous server state for node.
    def leave_fight(self):
        con = self.server_connect()
        con.send_line("CLEAR")
        con.close()
        return 1

    def attend_fight(self, mappings, node_ip, predictions, ntp, passive_sim=0):
        """
        This function is for starting and managing a fight
        once the details are known. It also handles the
        task of returning any valid connections (if any) that
        may be returned from threads in the simultaneous_fight function.
        """

        # Walk to fight.
        self.simultaneous_cons = []
        predictions = predictions.split(" ")
        self.simultaneous_fight(mappings, node_ip, predictions, ntp, passive_sim)
        
        # Return hole made in opponent.
        if len(self.simultaneous_cons):
            """
            There may be a problem here. I noticed that when these lines
            were removed during testing that connections tended to
            succeed more. There may be a lack of synchronization between
            the timing for connections to succeed so that a close on
            one side of the fight ends up ruining valid connections on
            this side. Will need to test more.

            Notes: the UNL synchronization code could actually fix
            this (potential) problem as a cool unintended side-effect.
            """

            # Close unneeded holes.
            """
            for i in range(1, len(self.simultaneous_cons)):
                try:
                    print("Closing unneeded hole")
                    #self.simultaneous_cons[i].s.close()
                except:
                    pass
            """

            try:
                # Return open hole.
                return self.simultaneous_cons[0]
            except:
                return None

        return None

    def sequential_connect(self):
        """
        Sequential connect is designed to return a connection to the
        Rendezvous Server but it does so in a way that the local port
        ranges (both for the server and used for subsequent hole
        punching) are allocated sequentially and predictably. This is
        because Delta+1 type NATs only preserve the delta value when
        the source ports increase by one.
        """

        # Connect to rendezvous server.
        try:
            mappings = sequential_bind(self.mapping_no + 1, self.interface)
            con = self.server_connect(mappings[0]["sock"])
        except Exception as e:
            print(e)
            print("this err")
            return None

        # First mapping is used to talk to server.
        mappings.remove(mappings[0])

        # Receive port mapping.
        msg = "SOURCE TCP %s" % (str(mappings[0]["source"]))
        con.send_line(msg)
        reply = con.recv_line(timeout=2)
        remote_port = self.parse_remote_port(reply)
        if not remote_port:
            return None

        # Generate port predictions.
        predictions = ""
        if self.nat_type != "random":
            mappings = self.predict_mappings(mappings)
            for mapping in mappings:
                predictions += str(mapping["remote"]) + " "
            predictions = predictions.rstrip()
        else:
            predictions = "1337"

        return [con, mappings, predictions]

    def simultaneous_listen(self):
        """
        This function is called by passive simultaneous nodes who
        wish to establish themself as such. It sets up a connection
        to the Rendezvous Server to monitor for new hole punching requests.
        """

        # Close socket.
        if self.server_con != None:
            self.server_con.s.close()
            self.server_con = None

        # Reset predictions + mappings.
        self.mappings = None
        self.predictions = None
        
        # Connect to rendezvous server.
        parts = self.sequential_connect()
        if parts == None:
            return 0
        con, mappings, predictions = parts
        con.blocking = 0
        con.timeout = 0
        con.s.settimeout(0)
        self.server_con = con
        self.mappings = mappings
        self.predictions = predictions

        # Register simultaneous node with server.
        msg = "SIMULTANEOUS READY 0 0"
        ret = self.server_con.send_line(msg)
        if not ret:
            return 0
        return 1

    def passive_listen(self, port, max_inbound=10):
        try:
            con = self.server_connect()
            msg = "PASSIVE READY %s %s" % (str(port), str(max_inbound))
            con.send_line(msg)
            con.close()
            return 1
        except:
            return 0

    def predict_mappings(self, mappings):
        """
        This function is used to predict the remote ports that a NAT
        will map a local connection to. It requires the NAT type to
        be determined before use. Current support for preserving and
        delta type mapping behaviour.
        """
        if self.nat_type not in self.predictable_nats:
            raise Exception("Can't predict mappings for non-predictable NAT type.")

        for mapping in mappings:
            mapping["bound"] = mapping["sock"].getsockname()[1]

            if self.nat_type == "preserving":
                mapping["remote"] = mapping["source"]
            
            if self.nat_type == "delta":
                max_port = 65535
                mapping["remote"] = int(mapping["source"]) + self.delta

                # Overflow or underflow = wrap port around.
                if mapping["remote"] > max_port:
                    mapping["remote"] = mapping["remote"] - max_port
                if mapping["remote"] < 0:
                    mapping["remote"] = max_port - -mapping["remote"]

                # Unknown error.
                if mapping["remote"] < 1 or mapping["remote"] > max_port:
                    mapping["remote"] = 1
                mapping["remote"] = str(mapping["remote"])

        return mappings

    def throw_punch(self, args):
        """
        Attempt to open a hole by TCP hole punching. This
        function is called by the simultaneous fight function
        and its the code that handles doing the actual hole
        punching / connecting.
        """

        # Parse arguments.
        if len(args) != 3:
            return 0
        sock, node_ip, remote_port = args
        if sock == None or node_ip == None or remote_port == None:
            return 0

        # Generous timeout.
        con = Sock(blocking=1, interface=self.interface)
        con.set_sock(sock)
        local = 0
        if is_ip_private(node_ip):
            """
            When simulating nodes on the same computer a delay needs to be set for the loop back interface to simulate the delays that occur over a WAN link. This requirement may also be needed for nodes on a LAN.

            sudo tc qdisc replace dev lo root handle 1:0 netem delay 0.5sec

            Speculation: The simulation problem may be to do with CPU cores. If the program is run on the same core then the connects will always be out of synch. If that's the case -- tries will need to be set to ~1000 which was what it was before. Perhaps a delay could be simulated by sleeping for random periods if its a local connection? That could help punch through at least once and then just set the tries to >= 1000.
            """
            tries = 20 # 20
            local = 1
        else:
            tries = 1

        source_port = sock.getsockname()[1]
        error = 0
        for i in range(0, tries):
            """
            if local:
                time.sleep(float(random.randrange(0, 500)) / 1000)
            """
            try:
                # Attempt to connect.
                con.connect(node_ip, remote_port)

                # FATALITY.

                # Atomic operation so mutex not required.
                # Record hole made.
                con.blocking = 0
                con.timeout = 0
                con.s.settimeout(0)
                self.simultaneous_cons.append(con)
                return 1
            except Exception as e:
                # Punch was blocked, opponent is strong.
                error = 1
                continue

        if error:
            sock.close()

        return 0

    def simultaneous_fight(self, my_mappings, node_ip, predictions, their_ntp, passive_sim=0):
        """
        TCP hole punching algorithm. It uses network time servers to
        synchronize two nodes to connect to each other on their
        predicted remote ports at the exact same time.

        One thing to note is how sensitive TCP hole punching is to
        timing. To open a successful connection both sides need to
        have their SYN packets cross the NAT before the other side's
        SYN arrives. Round-trip time for connections is 0 - 1000ms
        depending on proximity. That's a very small margin of error
        for hole punching, hence using NTP.

        See "TCP Hole Punching" http://www.ietf.org/rfc/rfc5128.txt
        and http://en.wikipedia.org/wiki/TCP_hole_punching
        for more details.
        """


        # Get current network time accurate to ~50 ms over WAN (apparently.)
        if passive_sim:
            # We're the one accepting the con + specifying the time.
            our_ntp = their_ntp
        else:
            # They're the ones figuring out sleep relative to us.
            our_ntp = get_ntp()
            if our_ntp == None:
                return 0

        # Synchronize code execution to occur at their NTP time + delay.
        current = our_ntp
        future = float(their_ntp) + float(self.ntp_delay)
        sleep_time = future - current

        # Check sleep time:
        if sleep_time < 0:
            print("We missed the meeting! It happened " + str(-sleep_time) + "seconds ago!")
            return 0
        else:
            time.sleep(sleep_time)
        """
        Time.sleep isn't guaranteed to sleep for the time specified
        which could cause synchronisation to be off between nodes
        and different OS' as per the discretion of the task scheduler.
        Think of a better way to do the sleep. Maybe a loop? 
        """

        # Can you dodge my special?
        """
        Making this algorithm "multi-threaded" has the potential to
        ruin predicted mappings for delta type NATs and NATs that
        have no care for source ports and assign incremental
        ports no matter what.
        """
        for mapping in my_mappings:
            # Tried all predictions.
            prediction_len = len(predictions)
            if not prediction_len:
                break

            # Throw punch.
            prediction = predictions[0]
            self.throw_punch([mapping["sock"], node_ip, prediction])
            predictions.remove(prediction)

        return 1
        

    # Attempt to open an outbound connect through simultaneous open.
    def simultaneous_challenge(self, node_ip, node_port, proto):
        """
        Used by active simultaneous nodes to attempt to initiate
        a simultaneous open to a compatible node after retrieving
        its details from bootstrapping. The function advertises
        itself as a potential candidate to the server for the
        designated node_ip. It also waits for a response from the
        node (if any) and attends any arranged fights.
        """

        parts = self.sequential_connect()
        if parts == None:
            return None
        con, mappings, predictions = parts

        # Tell server to list ourselves as a candidate for node.
        msg = "CANDIDATE %s %s %s" % (node_ip, str(proto), predictions)
        con.send_line(msg)
        reply = con.recv_line(timeout=10)
        if "PREDICTION SET" not in reply:
            return None

        # Wait for node to accept and give us fight time.
        # FIGHT 192.168.0.1 4552 345 34235 TCP 123123123.1\
        reply = con.recv_line(timeout=10)
        con.s.close()
        parts = re.findall("^FIGHT ([0-9]+[.][0-9]+[.][0-9]+[.][0-9]+) ((?:[0-9]+\s?)+) (TCP|UDP) ([0-9]+(?:[.][0-9]+)?)$", reply)
        if not len(parts):
            print("Invalid parts length.")
            return None
        node_ip, predictions, proto, ntp = parts[0]
        return self.attend_fight(mappings, node_ip, predictions, ntp)

    def parse_remote_port(self, reply):
        """
        Parses a remote port from a Rendezvous Server's
        response.
        """

        remote_port = re.findall("^REMOTE (TCP|UDP) ([0-9]+)$", reply)
        if not len(remote_port):
            remote_port = 0
        else:
            remote_port = int(remote_port[0][1])
            if remote_port < 1 or remote_port > 65535:
                remote_port = 0
        return remote_port

    def delta_test(self, mappings):
        """
        This function is designed to find the most commonly occurring
        difference between a set of numbers given a predefined margin
        of error. Its complexity is due to the fact that it allows
        for port collisions which may occur during NAT mapping.
        Its therefore more fault tolerant than simply considering
        the difference between two numbers and hence more accurate
        at determining a delta type NAT.
        """

        # Calculate differences.
        mapping_no = len(mappings)
        differences = []
        for i in range(0, mapping_no):
            # Overflow.
            if i + 1 >= mapping_no:
                break
            differences.append(mappings[i + 1]["remote"] - mappings[i]["remote"])
        differences = list(set(differences))

        # Record delta pattern results.
        delta = 0
        for difference in differences:
            """
            Calculate matches relative to each number for each difference.
            The matches are relative to mappings[i]
            """
            masked = []
            for i in range(0, mapping_no):
                matches = 0
                for j in range(0, mapping_no):
                    # This is ourself.
                    if i == j:
                        continue

                    # Use value of mappings[i] to derive test value for mappings[j].
                    if i > j:
                        # How many bellow it?
                        test_val = mappings[i]["remote"] - (difference * (i - j))
                    else:
                        # How many above it?
                        test_val = mappings[i]["remote"] + (difference * (j - i))

                    # Pattern was predicted for relative comparison so increment matches.
                    if test_val == mappings[j]["remote"]:
                        matches += 1
                
                # Matches parses the minimum threshold so these don't count as collisions.
                if matches + 1 > self.port_collisions:
                    masked.append(mappings[i]["remote"])

            # Check number of collisions satisfies delta requirement.
            collision_no = mapping_no - len(masked)
            if collision_no > self.port_collisions:
                continue
            if collision_no == int(mapping_no) / 2 and not mapping_no % 2:
                """
                This means there's no way to be sure. The number of
                collisions can be just as high as the number of
                "successes", in which case it's a stalemate.
                """
                continue
            delta = difference
            break

        if delta:
            nat_type = "delta"
        else:
            nat_type = "random"

        ret = {
            "nat_type": nat_type,
            "delta": delta
        }

        return ret

    def determine_nat(self):
        """
        This function can predict 4 types of NATS.
        (Not adequately tested yet.)
        1. Preserving.
        Source port == remote port
        2. Delta.
        Remote port == source port + delta.
        3. Delta+1
        Same as delta but delta is only preserved when
        the source port increments by 1 (my understanding I
        may have misunderstood.)
        - This case is handled by manually using incremental,
        sequential ports for punching operations.
        4. Reuse.
        Same source port + addr == previous mapped remote port
        for that connection.

        Good NAT characteristic references and definitions:
[0] http://nutss.gforge.cis.cornell.edu/pub/imc05-tcpnat.pdf
[1] http://doc.cacaoweb.org/misc/cacaoweb-and-nats/nat-behavioral-specifications-for-p2p-applications/#tcpholepun
[2] http://www.deusty.com/2007/07/nat-traversal-port-prediction-part-2-of.html
http://www.researchgate.net/publication/239801764_Implementing_NAT_Traversal_on_BitTorrent
[3] http://en.wikipedia.org/wiki/TCP_hole_punching
        """
        # Already set.
        if self.nat_type != "unknown":
            return self.nat_type
        nat_type = "random"

        # Check collision ration.
        if self.port_collisions * 5 > self.nat_tests:
            raise Exception("Port collision number is too high compared to nat tests. Collisions must be in ratio 1 : 5 to avoid ambiguity in test results.")

        # Load mappings for preserving and delta tests.
        mappings = sequential_bind(self.nat_tests, self.interface)
        for i in range(0, self.nat_tests):
            con = self.server_connect(mappings[i]["sock"])
            con.send_line("SOURCE TCP " + str(mappings[i]["source"]))
            remote_port = self.parse_remote_port(con.recv_line(timeout=2))
            mappings[i]["remote"] = int(remote_port)
            con.s.close()

        # Preserving test.
        preserving = 0
        for mapping in mappings:
            if mapping["source"] == mapping["remote"]:
                preserving += 1
        if preserving >= (self.nat_tests - self.port_collisions):
            nat_type = "preserving"
            return nat_type

        # Delta test.
        delta_ret = self.delta_test(mappings)
        if delta_ret["nat_type"] != "random":
            # Save delta value.
            self.delta = delta_ret["delta"]

            return nat_type

        # Load mappings for reuse test.
        """
        Notes: This reuse test needs to ideally be performed against
        bootstrapping nodes on at least two different addresses and
        ports to each other because there are NAT types which
        allocate new mappings based on changes to these variables.
        """
        mappings = []
        for i in range(0, self.nat_tests):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('', 0))
            con = Sock(blocking=1, interface=self.interface)
            con.s = sock
            source_port = con.s.getsockname()[1]
            con = self.server_connect(sock)
            con.send_line("SOURCE TCP " + str(source_port))
            remote_port = self.parse_remote_port(con.recv_line(timeout=2))
            mappings.append({
                "source": source_port,
                "remote": int(remote_port)
            })
        if len(mappings) < self.nat_tests:
            return nat_type

        # Test reuse.
        reuse = 0
        for mapping in mappings:
            if mapping["source"] == mapping["remote"]:
                reuse += 1
        if reuse >= (self.nat_tests - self.port_collisions):
            nat_type = "reuse"

        return nat_type


if __name__ == "__main__":
    from pyp2p.net import rendezvous_servers
    client = RendezvousClient(nat_type="preserving", rendezvous_servers=rendezvous_servers)

