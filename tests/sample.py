import hashlib
import tempfile
from threading import Thread
from pyp2p.lib import *
from pyp2p.net import Net
from pyp2p.sys_clock import SysClock
if sys.version_info >= (3, 0, 0):
    from urllib.parse import urlparse
    import socketserver as SocketServer
    from http.server import HTTPServer
    from http.server import SimpleHTTPRequestHandler
else:
    from urlparse import urlparse
    import SocketServer
    from BaseHTTPServer import HTTPServer
    from SimpleHTTPServer import SimpleHTTPRequestHandler
from pyp2p.sock import Sock
from timeit import default_timer as timer

if sys.version_info >= (3, 0, 0):
    pass
else:
    pass

from pyp2p.rendezvous_server import RendezvousFactory
from pyp2p.rendezvous_client import RendezvousClient
from pyp2p.net import rendezvous_servers

from twisted.internet import reactor

# Test bootstrap
# Test challenge protocol for sim open
# Test rendezvous protocol
# All in same func due to twisted errors ...





import requests
import random
import binascii
from future.moves.urllib.parse import urlencode
# Todo use the old server for this.
