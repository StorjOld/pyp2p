import hashlib
import tempfile
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

if sys.version_info >= (3, 0, 0):
    pass
else:
    pass
