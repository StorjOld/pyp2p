import netifaces
import os
import struct
import sys
import time
import psutil
import gc
import ipaddress
import ntplib
import re
from future.moves.urllib.request import urlopen

import traceback
from .ipgetter import *
from .ip_routes import *

if platform.system() == "Linux":
    try:
        from pyroute2 import IPDB
        ip = IPDB()
    except IOError:
        ip = None
else:
    ip = None


def get_unused_port():
    """Checks if port is already in use."""
    port = random.randint(1024, 65535)
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('', port))  # Try to open port
    except socket.error as e:
        if e.errno in (98, 10048):  # 98, 10048 means address already bound
            return get_unused_port()
        raise e
    s.close()
    return port


def log_exception(file_path, msg):
    msg = "\r\n" + msg
    with open(file_path, "a") as error_log:
        error_log.write(msg)


def parse_exception(e, output=0):
    tb = traceback.format_exc()
    exc_type, exc_obj, exc_tb = sys.exc_info()
    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    error = "%s %s %s %s %s" % (str(tb), str(exc_type), str(fname),
                                str(exc_tb.tb_lineno), str(e))

    if output:
        print(error)

    return str(error)


def ip2int(addr):
    return struct.unpack("!I", socket.inet_aton(addr))[0]


def int2ip(addr):
    return socket.inet_ntoa(struct.pack("!I", addr))

# Patches for urllib2 and requests to bind on specific interface.
# http://rossbates.com/2009/10/26/urllib2-with-multiple-network-interfaces/
true_socket = socket.socket


def build_bound_socket(source_ip):
    def bound_socket(*a, **k):
        if source_ip == "127.0.0.1":
            raise Exception("This function requires a LAN IP"
                            " (127.0.0.1 passed.)")

        sock = true_socket(*a, **k)
        sock.bind((source_ip, 0))
        return sock

    return bound_socket


def busy_wait(dt):
    # Use most accurate timer.
    if platform.system() == "Windows":
        timer = time.clock
    else:
        timer = time.time

    current_time = timer()
    while timer() < current_time + dt:
        pass


def get_ntp_worker(server):
    try:
        client = ntplib.NTPClient()
        response = client.request(server, version=3)
        ntp = response.tx_time
        return ntp
    except Exception as e:
        return None

ntp_servers = [
    "pool.ntp.org",
    "2.pool.ntp.org",
    "0.pool.ntp.org",
    "1.pool.ntp.org",
    "3.pool.ntp.org"
]

bad_ntp_servers = None


def remove_bad_ntp_servers():
    global ntp_servers
    global bad_ntp_servers

    bad_ntp_servers = []
    for server in ntp_servers:
        ntp = get_ntp_worker(server)
        if ntp is None:
            bad_ntp_servers.append(server)

    for server in bad_ntp_servers:
        ntp_servers.remove(server)


def get_ntp(local_time=0):
    global ntp_servers
    global bad_ntp_servers

    if local_time:
        return time.time()

    if bad_ntp_servers is None:
        remove_bad_ntp_servers()

    random.shuffle(ntp_servers, random.random)
    for server in ntp_servers:
        ntp = get_ntp_worker(server)
        if ntp is not None:
            return ntp

    return None


def get_default_gateway(interface="default"):
    if sys.version_info < (3, 0, 0):
        if type(interface) == str:
            interface = unicode(interface)
    else:
        if type(interface) == bytes:
            interface = interface.decode("utf-8")

    if platform.system() == "Windows":
        if interface == "default":
            default_routes = [r for r in get_ipv4_routing_table()
                              if r[0] == '0.0.0.0']
            if default_routes:
                return default_routes[0][2]

    try:
        gws = netifaces.gateways()
        if sys.version_info < (3, 0, 0):
            return gws[interface][netifaces.AF_INET][0].decode("utf-8")
        else:
            return gws[interface][netifaces.AF_INET][0]
    except:
        # This can also mean the machine is directly accessible.
        return None


def get_lan_ip(interface="default"):
    if sys.version_info < (3, 0, 0):
        if type(interface) == str:
            interface = unicode(interface)
    else:
        if type(interface) == bytes:
            interface = interface.decode("utf-8")

    # Get ID of interface that handles WAN stuff.
    default_gateway = get_default_gateway(interface)
    gateways = netifaces.gateways()
    wan_id = None
    if netifaces.AF_INET in gateways:
        gw_list = gateways[netifaces.AF_INET]
        for gw_info in gw_list:
            if gw_info[0] == default_gateway:
                wan_id = gw_info[1]
                break

    # Find LAN IP of interface for WAN stuff.
    interfaces = netifaces.interfaces()
    if wan_id in interfaces:
        families = netifaces.ifaddresses(wan_id)
        if netifaces.AF_INET in families:
            if_info_list = families[netifaces.AF_INET]
            for if_info in if_info_list:
                if "addr" in if_info:
                    return if_info["addr"]

    """
    Execution may reach here if the host is using
    virtual interfaces on Linux and there are no gateways
    which suggests the host is a VPS or server. In this
    case
    """
    if platform.system() == "Linux":
        if ip is not None:
            return ip.routes["8.8.8.8"]["prefsrc"]

    return None


def sequential_bind(n, interface="default"):
    # Get bind address.
    addr = ''
    if interface != "default":
        addr = get_lan_ip(interface)

    # Start the process.
    bound = 0
    mappings = []
    prospects = []
    while not bound:
        # Grab a random place to start.
        bound = 1
        start = random.randrange(1024, 65535 - n)

        # Use connect to see if its already bound.
        for i in range(0, n):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            local = start + i
            try:
                sock.connect((addr, local))
                sock.close()
                bound = 0
                break
            except socket.error:
                pass

            prospect = {
                "local": local,
            }
            prospects.append(prospect)

        for prospect in prospects:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((addr, prospect["local"]))
            except Exception as e:
                bound = 0
                for mapping in mappings:
                    mapping["sock"].close()
                mappings = []
                break

            mapping = {
                "source": prospect["local"],
                "sock": sock
            }
            mappings.append(mapping)

    return mappings


def is_port_forwarded(source_ip, port, proto, forwarding_servers):
    global true_socket
    if source_ip is not None:
        socket.socket = build_bound_socket(source_ip)

    ret = 0
    for forwarding_server in forwarding_servers:
        url = "http://" + forwarding_server["addr"] + ":"
        url += str(forwarding_server["port"])
        url += forwarding_server["url"]
        url += "?action=is_port_forwarded&port=" + str(port)
        url += "&proto=" + str(proto.upper())

        try:
            r = urlopen(url, timeout=2)
            response = r.read().decode("utf-8")
            if "yes" in response:
                ret = 1
                break
        except:
            continue

    socket.socket = true_socket
    return ret


def is_ip_private(ip_addr):
    if sys.version_info < (3, 0, 0):
        if type(ip_addr) == str:
            ip_addr = unicode(ip_addr)
    else:
        if type(ip_addr) == bytes:
            ip_addr = ip_addr.decode("utf-8")

    if ipaddress.ip_address(ip_addr).is_private and ip_addr != "127.0.0.1":
        return 1
    else:
        return 0


def is_ip_public(ip_addr):
    if sys.version_info < (3, 0, 0):
        if type(ip_addr) == str:
            ip_addr = unicode(ip_addr)
    else:
        if type(ip_addr) == bytes:
            ip_addr = ip_addr.decode("utf-8")

    if is_ip_private(ip_addr):
        return 0
    elif ip_addr == "127.0.0.1":
        return 0
    else:
        return 1


def is_ip_valid(ip_addr):
    if sys.version_info < (3, 0, 0):
        if type(ip_addr) == str:
            ip_addr = unicode(ip_addr)
    else:
        if type(ip_addr) == bytes:
            ip_addr = ip_addr.decode("utf-8")

    try:
        ipaddress.ip_address(ip_addr)
        return 1
    except:
        return 0


def is_valid_port(port):
    try:
        port = int(port)
    except:
        return 0
    if port < 1 or port > 65535:
        return 0
    else:
        return 1


def memoize(function):
    memo = {}

    def wrapper(*args):
        if args in memo:
            return memo[args]
        else:
            rv = function(*args)
            memo[args] = rv
            return rv
    return wrapper


def extract_ip(s):
    ip = re.findall("[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+", s)
    if len(ip):
        return ip[0]

    return ""


@memoize
def get_wan_ip(n=0):
    """
    That IP module sucks. Occasionally it returns an IP address behind
    cloudflare which probably happens when cloudflare tries to proxy your web
    request because it thinks you're trying to DoS. It's better if we just run
    our own infrastructure.
    """

    if n == 2:
        try:
            ip = myip()
            ip = extract_ip(ip)
            if is_ip_valid(ip):
                return ip
        except Exception as e:
            print(str(e))
            return None

    # Fail-safe: use centralized server for IP lookup.
    from pyp2p.net import forwarding_servers
    for forwarding_server in forwarding_servers:
        url = "http://" + forwarding_server["addr"] + ":"
        url += str(forwarding_server["port"])
        url += forwarding_server["url"]
        url += "?action=get_wan_ip"
        try:
            r = urlopen(url, timeout=5)
            response = r.read().decode("utf-8")
            response = extract_ip(response)
            if is_ip_valid(response):
                return response
        except Exception as e:
            print(str(e))
            continue

    time.sleep(1)
    return get_wan_ip(n + 1)


def request_priority_execution():
    gc.disable()
    sys.setcheckinterval(999999999)
    if sys.version_info > (3, 0, 0):
        sys.setswitchinterval(1000)
    p = psutil.Process(os.getpid())
    try:
        if platform.system() == "Windows":
            p.nice(psutil.HIGH_PRIORITY_CLASS)
        else:
            p.nice(10)
    except psutil.AccessDenied:
        pass

    return p


def release_priority_execution(p):
    sys.setcheckinterval(100)
    if sys.version_info > (3, 0, 0):
        sys.setswitchinterval(0.005)
    try:
        if platform.system() == "Windows":
            p.nice(psutil.NORMAL_PRIORITY_CLASS)
        else:
            p.nice(5)
    except psutil.AccessDenied:
        pass
    gc.enable()


def encode_str(s, encoding="unicode"):
    # Encode unsafe binary to unicode
    # Encode unsafe unicode to binary
    if sys.version_info >= (3, 0, 0):
        # str in Python 3+ is unicode.
        if type(s) == str:
            if encoding == "ascii":
                # Encodes unicode directly as bytes.
                codes = []
                for ch in s:
                    codes.append(ord(ch))

                if len(codes):
                    return bytes(codes)
                else:
                    return b""
        else:
            # bytes
            if encoding == "unicode":
                # Converts bytes to unicode.
                return s.decode("utf-8")
    else:
        # unicode in python 2 is unicode.
        if type(s) == unicode:
            # Encodes unicode directly as bytes.
            if encoding == "ascii":
                byte_str = b""
                for ch in s:
                    byte_str += chr(ord(ch))

                return byte_str
        else:
            # bytes.
            if encoding == "unicode":
                # Converts bytes to unicode.
                return s.decode("utf-8")

    if type(s) == type(u""):
        s = s.encode("utf-8")

    return s

if __name__ == "__main__":
    # print(get_wan_ip())
    # pass
    print("In lib")

