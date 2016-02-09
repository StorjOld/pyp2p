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
from timeit import default_timer as timer

if sys.version_info >= (3, 0, 0):
    pass
else:
    pass

def md5sum(fname):
    my_hash = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            my_hash.update(chunk)
    return my_hash.hexdigest()


class SockDownload:
    def __init__(self, url, expected_hash, file_size, blocking=0,
                 encoding="unicode"):
        """
        Download a file from a HTTP URL and compare it to an MD5 hash.
        Uses the sock.py module for testing.

        :param url: URL to download
        :param expected_hash: MD5 hash of file (md5sum file from term)
        :param file_size: size in bytes of the file to download
        :param blocking: use blocking or non-blocking sockets
        :return:
        """

        url = urlparse(url)
        location = url.netloc.split(":")
        if len(location) == 1:
            port = 80
            host, = location
        else:
            host, port = location

        con = Sock(host, port, blocking=0)
        req = self.build_request(host, url.path)
        con.send(req, send_all=1)
        buf = u""
        eof = u"\r\n\r\n"
        while buf != eof and con.connected:
            ch = con.recv(1)
            if len(ch):
                buf += ch

            eq = 0
            for i in range(0, len(buf)):
                if buf[i] != eof[eq]:
                    eq = 0
                else:
                    eq += 1

            # Reset buf.
            if eq == len(eof):
                break

        fp, path = tempfile.mkstemp()
        os.close(fp)
        remaining = file_size
        total = 0
        self.start_time = timer()
        with open(path, "ab") as fp:
            future = time.time() + 30 # Slow connections are slow.
            while con.connected:
                chunk_size = 2048
                if chunk_size < remaining:
                    chunk_size = remaining
                data = con.recv(chunk_size, encoding=encoding)
                if len(data):
                    remaining -= len(data)
                    total += len(data)

        found_hash = md5sum(path)
        os.remove(path)
        if expected_hash is not None:
            assert(found_hash == expected_hash)

        self.total = total

    def build_request(self, host, resource):
        req = "GET %s HTTP/1.1\r\n" % resource
        req += "Host: %s\r\n" % host
        req += "Connection: close\r\n\r\n"

        return req

fs = 10485760
sd = SockDownload(
    url="http://cachefly.cachefly.net/10mb.test",
    expected_hash=None,
    file_size=fs
)
x = sd.start_time
y = timer()
print(fs)

"""
x = time.time()
import urllib2,cookielib

site= "http://ipv4.download.thinkbroadband.com/20MB.zip"
hdr = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.11 (KHTML, like Gecko) Chrome/23.0.1271.64 Safari/537.11',
       'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
       'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.3',
       'Accept-Encoding': 'none',
       'Accept-Language': 'en-US,en;q=0.8',
       'Connection': 'keep-alive'}

req = urllib2.Request(site, headers=hdr)

try:
    page = urllib2.urlopen(req)
except urllib2.HTTPError, e:
    print e.fp.read()

content = page.read()
"""

y = time.time()


speed = (((fs / (y - x)) / 1024) / 1024) * 8
#print(fs)
print(speed)


