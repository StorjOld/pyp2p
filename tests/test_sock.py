"""
* Test whether multiple recvs on the same connection (non-blocking) will eventually have the connection closed (use another net instance.)

* Test whether multiple sends on the same connection (non-blocking) will eventually lead to the connection being closed (use a net instance with no recvs! and loop over the cons)

(Not implemented for now since these will greatly slow the build.)
"""

from unittest import TestCase
from pyp2p.sock import *
from pyp2p.rendezvous_client import RendezvousClient
from pyp2p.net import rendezvous_servers
import time
import sys
import random
import os
import tempfile
import hashlib
if sys.version_info >= (3, 0, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse


class test_sock(TestCase):
    def test_http_upload_post(self):
        class SockUpload():
            def __init__(self, upload_size, blocking=0):
                host = u"185.86.149.128"
                port = 80
                resource = u"/upload_test.php"
                content = self.build_content(upload_size)
                con = Sock(host, port, blocking=blocking)
                req = self.build_request(host, resource, content)
                con.send(req, send_all=1)

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
                req  = "POST %s HTTP/1.1\r\n" % (resource)
                req += "Host: %s\r\n" % (host)
                req += "User-Agent: Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:42.0) Gecko/20100101 Firefox/42.0\r\n"
                req += "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n"
                req += "Accept-Language: en-US,en;q=0.5\r\n"
                req += "Accept-Encoding: gzip, deflate\r\n"
                req += "Connection: keep-alive\r\n"
                req += "Content-Type: application/x-www-form-urlencoded\r\n"
                req += "Content-Length: %d\r\n\r\n" % (len(content) + 5)
                req += "test=" # Hence the extra + 5.

                return req

            def build_content(self, upload_size):
                content = b"8" * upload_size

                return content

        SockUpload(1000 * 100)

    def test_http_download(self):
        def md5sum(fname):
            hash = hashlib.md5()
            with open(fname, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash.update(chunk)
            return hash.hexdigest()


        class SockDownload():
            def __init__(self, url, expected_hash, file_size, blocking=0):
                """
                Download a file from a HTTP URL and compare it to an MD5 hash. Uses the sock.py module for testing.

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

                con = Sock(host, port, blocking=blocking)
                req = self.build_request(host, url.path)
                con.send(req, send_all=1)
                buf = u""
                eof = u"\r\n\r\n"
                while buf != eof:
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
                    while con.connected and remaining:
                        data = con.recv(remaining, encoding="ascii")
                        if len(data):
                            remaining -= len(data)
                            fp.write(data)
                        time.sleep(0.0002)

                found_hash = md5sum(path)
                os.remove(path)
                assert(found_hash == expected_hash)

            def build_request(self, host, resource):
                req  = "GET %s HTTP/1.1\r\n" % (resource)
                req += "Host: %s\r\n\r\n" % (host)

                return req


        SockDownload(
            "http://mirror.internode.on.net/pub/test/1meg.test",
            "e6527b4d5db05226f40f9f2e7750abfb",
            1000000
        )


    def test_blocking_mode(self):
        x = Sock()
        blocking = x.s.gettimeout()

        if x.blocking:
            assert(blocking >= 1 or blocking == None)
        else:
            assert(blocking == 0.0)

        x.close()
        x = Sock(blocking=1)

        blocking = x.s.gettimeout()
        if x.blocking:
            assert(blocking >= 1 or blocking == None)
        else:
            assert(blocking == 0.0)

        x.close()
        x = Sock("www.example.com", 80)

        blocking = x.s.gettimeout()
        if x.blocking:
            assert(blocking >= 1 or blocking == None)
        else:
            assert(blocking == 0.0)

        x.close()
        x = Sock("www.example.com", 80, blocking=1)

        blocking = x.s.gettimeout()
        if x.blocking:
            assert(blocking >= 1 or blocking == None)
        else:
            assert(blocking == 0.0)

        x.close()


    def test_blocking_timeout(self):
        client = RendezvousClient(nat_type="preserving", rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        t = time.time()
        s.recv_line(timeout=1)
        if time.time() - t >= 4:
            print("Manual timeout failed.")
            assert(0)
        s.close()

    def test_non_blocking_timeout(self):
        client = RendezvousClient(nat_type="preserving", rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        assert(s.recv_line() == u"")
        assert(s.recv(1) == u"")
        s.close()

    def test_encoding(self):
        client = RendezvousClient(nat_type="preserving", rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        s.send_line("SOURCE TCP 50")
        ret = s.recv(1, encoding="ascii")
        if sys.version_info >= (3,0,0):
            assert(type(ret) == bytes)
        else:
            assert(type(ret) == str)
        assert(ret == b"R")
        ret = s.recv_line()
        assert(u"EMOTE" in ret)
        s.close()

    def test_recv_recvline_switch(self):
        client = RendezvousClient(nat_type="preserving", rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        s.send_line("SOURCE TCP 32")
        ret = s.recv(1)
        assert(ret[0] == u"R")
        assert(not len(s.buf))
        s.buf = u"test"
        ret = s.recv(1)
        assert(ret[0] == u"E")
        assert(s.buf == u"test")
        s.buf = u"example\r\nxsfsdf"
        junk = s.buf[:]
        s.send_line("SOURCE TCP 50")

        ret = s.recv_line()
        print(ret)
        assert("example" in ret)
        print(s.buf)
        print(junk)
        ret = s.recv_line()
        assert("xsfsdf" in ret)
        print(s.buf)
        print(junk)
        ret = s.recv_line()
        assert("MOTE" in ret)

        s.close()

    def test_0000001_sock(self):
        client = RendezvousClient(nat_type="preserving", rendezvous_servers=rendezvous_servers)
        s = client.server_connect()
        assert (s.connected)
        s.send_line("SOURCE TCP 323")
        assert (s.connected)
        line = s.recv_line()
        assert ("REMOTE" in line)

        s = Sock("www.example.com", 80, blocking=0, timeout=5)
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

        s = Sock("www.example.com", 80, blocking=1, timeout=5)
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
        s.buf = "\r\nx\r\n"
        x = s.parse_buf()
        assert (x[0] == "x")

        s.buf = "\r\n"
        x = s.parse_buf()
        assert (x == [])

        s.buf = "\r\n\r\n"
        x = s.parse_buf()
        assert (x == [])

        s.buf = "\r\r\n\r\n"
        x = s.parse_buf()
        assert (x[0] == "\r")

        s.buf = "\r\n\r\n\r\nx"
        x = s.parse_buf()
        assert (x == [])

        s.buf = "\r\n\r\nx\r\nsdfsdfsdf\r\n"
        x = s.parse_buf()
        assert (x[0] == "x" and x[1] == "sdfsdfsdf")

        s.buf = "sdfsdfsdf\r\n"
        s.parse_buf()
        s.buf += "abc\r\n"
        x = s.parse_buf()
        assert (x[0] == "abc")

        s.buf += "\r\ns\r\n"
        x = s.parse_buf()
        assert (x[0] == "s")

        s.buf = "reply 1\r\nreply 2\r\n"
        s.replies = []
        s.update()
        assert (s.pop_reply(), "reply 1")
        assert (s.replies[0], "reply 2")
