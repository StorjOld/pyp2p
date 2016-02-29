"""
* Test whether multiple recvs on the same connection (non-blocking) will
 eventually have the connection closed (use another net instance.)

* Test whether multiple sends on the same connection (non-blocking) will
 eventually lead to the connection being closed (use a net instance with
 no recvs! and loop over the cons)

(Not implemented for now since these will greatly slow the build.)
"""

import hashlib
import os
import tempfile
from threading import Thread
from unittest import TestCase

from pyp2p.net import rendezvous_servers
from pyp2p.rendezvous_client import RendezvousClient
from pyp2p.sock import *

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


class ThreadingSimpleServer(
    SocketServer.ThreadingMixIn,
    HTTPServer
):
    pass


def md5sum(fname):
    my_hash = hashlib.md5()
    with open(fname, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            my_hash.update(chunk)
    return my_hash.hexdigest()


class SockDownload:
    def __init__(self, url, expected_hash, file_size, blocking=0,
                 encoding="ascii"):
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

        con = Sock(host, port, blocking=blocking, debug=1)
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
        with open(path, "ab") as fp:
            future = time.time() + 30 # Slow connections are slow.
            while con.connected and remaining:
                data = con.recv(remaining, encoding=encoding)
                print(type(data))
                if len(data):
                    remaining -= len(data)
                    fp.write(data)
                time.sleep(0.0002)

                # Fail safe:
                if time.time() >= future:
                    break

        found_hash = md5sum(path)
        os.remove(path)
        if expected_hash is not None:
            assert(found_hash == expected_hash)

    def build_request(self, host, resource):
        req = "GET %s HTTP/1.1\r\n" % resource
        req += "Host: %s\r\n\r\n" % host

        return req


class SockUpload:
    def __init__(self, upload_size, blocking=0):
        host = u"185.86.149.128"
        port = 80
        resource = u"/upload_test.php"
        content = self.build_content(upload_size)
        con = Sock(host, port, blocking=blocking, debug=1)
        req = self.build_request(host, resource, content)
        con.send(req, send_all=1, timeout=6)

        # Now do the actual upload.
        remaining = upload_size
        chunk_size = 4096
        while con.connected and remaining:
            sent = upload_size - remaining
            msg = content[sent:sent + chunk_size]
            sent = con.send(msg)
            if sent:
                remaining -= sent

        # Get response.
        con.set_blocking(1)
        ret = con.recv(1024)

        # Check response.
        expected_hash = hashlib.sha256(content).hexdigest()
        assert(expected_hash in ret)

    def build_request(self, host, resource, content):
        req = "POST %s HTTP/1.1\r\n" % resource
        req += "Host: %s\r\n" % host
        req += "User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:42.0) "
        req += "Gecko/20100101 Firefox/42.0\r\n"
        req += "Accept: text/html,"
        req += "application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
        req += "Accept-Language: en-US,en;q=0.5\r\n"
        req += "Accept-Encoding: gzip, deflate\r\n"
        req += "Connection: keep-alive\r\n"
        req += "Content-Type: application/x-www-form-urlencoded\r\n"
        req += "Content-Length: %d\r\n\r\n" % (len(content) + 5)
        req += "test="  # Hence the extra + 5.

        return req

    def build_content(self, upload_size):
        content = b"8" * upload_size

        return content


def simple_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost', 9000))
    s.listen(0)
    (clientsocket, address) = s.accept()
    time.sleep(2)
    s.close()


class TestSock(TestCase):
    def test_http_upload_post(self):
        SockUpload(1000 * 100)

    def test_http_download(self):
        SockDownload(
            "http://mirror.internode.on.net/pub/test/1meg.test",
            "e6527b4d5db05226f40f9f2e7750abfb",
            1000000
        )

    def test_blocking_mode(self):
        x = Sock()
        blocking = x.s.gettimeout()

        if x.blocking:
            assert(blocking >= 1 or blocking is None)
        else:
            assert(blocking == 0.0)

        x.close()
        x = Sock(blocking=1)

        blocking = x.s.gettimeout()
        if x.blocking:
            assert(blocking >= 1 or blocking is None)
        else:
            assert(blocking == 0.0)

        x.close()
        x = Sock("www.example.com", 80, timeout=10)

        blocking = x.s.gettimeout()
        if x.blocking:
            assert(blocking >= 1 or blocking is None)
        else:
            assert(blocking == 0.0)

        x.close()
        x = Sock("www.example.com", 80, blocking=1, timeout=10)

        blocking = x.s.gettimeout()
        if x.blocking:
            assert(blocking >= 1 or blocking is None)
        else:
            assert(blocking == 0.0)

        x.close()

    def test_blocking_timeout(self):
        # "Pending issue https://github.com/Storj/pyp2p/issues/29"
        return
        client = RendezvousClient(nat_type="preserving",
                                  rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        t = time.time()
        s.recv_line(timeout=1)
        if time.time() - t >= 4:
            print("Manual timeout failed.")
            assert 0
        s.close()

    def test_non_blocking_timeout(self):
        client = RendezvousClient(nat_type="preserving",
                                  rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        assert(s.recv_line() == u"")
        assert(s.recv(1) == u"")
        s.close()

    def test_encoding(self):
        client = RendezvousClient(nat_type="preserving",
                                  rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        s.send_line("SOURCE TCP 50")
        ret = s.recv(1, encoding="ascii")
        if sys.version_info >= (3, 0, 0):
            assert(type(ret) == bytes)
        else:
            assert(type(ret) == str)
        assert(ret == b"R")
        ret = s.recv_line()
        assert(u"EMOTE" in ret)
        s.send_line("SOURCE TCP 50")
        ret = s.recv(1, encoding="unicode")
        if sys.version_info >= (3, 0, 0):
            assert(type(ret) == str)
        else:
            assert(type(ret) == unicode)
        s.close()

    def test_0000001_sock(self):
        client = RendezvousClient(nat_type="preserving",
                                  rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        assert s.connected
        s.send_line("SOURCE TCP 323")
        assert s.connected
        line = s.recv_line()
        assert ("REMOTE" in line)

        s = Sock("www.example.com", 80, blocking=0, timeout=10)
        data = "GET / HTTP/1.1\r\n"
        data += "Connection: close\r\n"
        data += "Host: www.example.com\r\n\r\n"
        s.send(data, send_all=1)
        replies = ""
        while s.connected:
            for reply in s:
                # Output should be unicode.
                if sys.version_info >= (3, 0, 0):
                    assert (type(reply) == str)
                else:
                    assert (type(reply) == unicode)

                replies += reply
                print(reply)

        assert (s.connected != 1)
        assert (replies != "")

        s.close()
        s.reconnect()
        s.close()

        s = Sock("www.example.com", 80, blocking=1, timeout=10)
        s.send_line("GET / HTTP/1.1")
        s.send_line("Host: www.example.com\r\n")
        line = s.recv_line()
        print(line)
        print(type(line))
        print(s.buf)
        print(type(s.buf))
        assert (line, "HTTP/1.1 200 OK")
        if sys.version_info >= (3, 0, 0):
            assert (type(line) == str)
        else:
            assert (type(line) == unicode)
        s.close()

        s = Sock()
        s.buf = b"\r\nx\r\n"
        x = s.parse_buf()
        assert (x[0] == "x")

        s.buf = b"\r\n"
        x = s.parse_buf()
        assert (x == [])

        s.buf = b"\r\n\r\n"
        x = s.parse_buf()
        assert (x == [])

        s.buf = b"\r\r\n\r\n"
        x = s.parse_buf()
        assert (x[0] == "\r")

        s.buf = b"\r\n\r\n\r\nx"
        x = s.parse_buf()
        assert (x == [])

        s.buf = b"\r\n\r\nx\r\nsdfsdfsdf\r\n"
        x = s.parse_buf()
        assert (x[0] == "x" and x[1] == "sdfsdfsdf")

        s.buf = b"sdfsdfsdf\r\n"
        s.parse_buf()
        s.buf += b"abc\r\n"
        x = s.parse_buf()
        assert (x[0] == "abc")

        s.buf += b"\r\ns\r\n"
        x = s.parse_buf()
        assert (x[0] == "s")

        s.buf = b"reply 1\r\nreply 2\r\n"
        s.replies = []
        s.update()
        assert (s.pop_reply(), "reply 1")
        assert (s.replies[0], "reply 2")

    def test_keep_alive(self):
        old_system = platform.system
        for os in ["Darwin", "Windows", "Linux"]:
            def system_wrapper():
                return os

            platform.system = system_wrapper
            sock = Sock()

            # Sock option error - not supported on this OS.
            try:
                sock.set_keep_alive(sock.s)
            except socket.error as e:
                valid_errors = (10042, 22)
                if e.errno not in valid_errors:
                    raise e

            except AttributeError:
                pass

            sock.close()

        platform.system = old_system
        assert 1

    def test_non_default_iface(self):
        sock = Sock(interface="eth12")
        try:
            sock.connect("www.example.com", 80, timeout=10)
        except (TypeError, socket.error) as e:
            pass
        sock.close()
        assert 1

    def test_ssl(self):
        s = Sock(
            "www.example.com",
            443,
            blocking=0,
            timeout=10,
            use_ssl=1

        )
        data = "GET / HTTP/1.1\r\n"
        data += "Connection: close\r\n"
        data += "Host: www.example.com\r\n\r\n"
        s.send(data, send_all=1)
        replies = ""
        while s.connected:
            for reply in s:
                # Output should be unicode.
                if sys.version_info >= (3, 0, 0):
                    assert (type(reply) == str)
                else:
                    assert (type(reply) == unicode)

                replies += reply
                print(reply)

        assert (s.connected != 1)
        assert (replies != "")

    def test_ssl_blocking_error(self):
        # Blocking.
        s = Sock(
            "www.example.com",
            443,
            blocking=1,
            timeout=2,
            use_ssl=1,
            debug=1
        )
        s.get_chunks()
        s.close()

        # Non-blocking.
        s = Sock(
            "www.example.com",
            443,
            blocking=0,
            timeout=2,
            use_ssl=1,
            debug=1
        )
        s.get_chunks()
        s.close()

    def test_decoding_error(self):
        SockDownload(
            "http://mirror.internode.on.net/pub/test/1meg.test",
            expected_hash=None,
            file_size=1000,
            blocking=0,
            encoding="unicode"
        )

    def test_broken_send_con(self):
        # Can't monkey patch socket on Linux.
        if platform.system != "Windows":
            return

        port = 10121
        server = ThreadingSimpleServer(('', port), SimpleHTTPRequestHandler)
        sock = Sock("127.0.0.1", port, debug=1, timeout=6)
        server.server_close()
        print(sock.send(b"test"))
        sock.close()

        server = ThreadingSimpleServer(('', port), SimpleHTTPRequestHandler)

        def close_server():
            time.sleep(1)
            server.server_close()

        sock = Sock("127.0.0.1", port, debug=1, timeout=6)
        Thread(target=close_server).start()
        for i in range(0, 5):
            print(sock.send(b"test"))
            time.sleep(0.5)
        sock.close

        # Simulate send timeout!
        sock = Sock(debug=1, blocking=1)

        def raise_timeout():
            time.sleep(1)
            original_send = sock.s.send

            def fake_send(data):
                raise socket.timeout("timed out")

            sock.s.send = fake_send
            time.sleep(1)
            sock.s.send = original_send

        Thread(target=raise_timeout).start()
        sock.connect("www.example.com", 80)

        # You want to fill up the entire networking buffer
        # so that it times out without the needed recv.
        buf_size = sock.s.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF) + 1
        buf_size *= 2
        sock.chunk_size = buf_size
        total = 0
        for i in range(0, 4):
            x = sock.send(b"x" * buf_size)
            total += x
            if x < buf_size:
                break

        time.sleep(2.2)
        sock.close()

        # Test broken connection.
        sock = Sock(debug=1, blocking=1)

        def raise_timeout():
            time.sleep(1)
            original_send = sock.s.send

            def fake_send(data):
                return 0

            sock.s.send = fake_send
            time.sleep(1)

        Thread(target=raise_timeout).start()
        sock.connect("www.example.com", 80)

        # You want to fill up the entire networking buffer
        # so that it times out without the needed recv.
        x = 1
        timeout = time.time() + 10
        while x and time.time() < timeout:
            x = sock.send(b"x")

        time.sleep(2.2)
        sock.close()

    def test_magic(self):
        sock = Sock()
        sock.replies = ["a", "b", "c"]
        assert(len(sock) == 3)
        assert(sock[0] == "a")
        del sock[0]
        assert(sock[0] == "b")
        sock[0] = "x"
        assert(sock[0] == "x")
        y = list(reversed(sock))
        assert(y == ["x", "c"])
