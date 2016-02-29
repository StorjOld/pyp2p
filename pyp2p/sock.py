"""
Implements a custom protocol for sending and receiving
line delineated messages. For blocking sockets,
time-out is required to avoid DoS attacks when talking
to a misbehaving or malicious third party.

The benefit of this class is it makes communication
with the P2P network easy to code without having to
depend on threads and hence on mutexes (which are hard
to use correctly.)

In practice, a connection to a node on the P2P network
would be done using the default options of this class
and the connection would periodically be polled for
replies. The processing of replies would automatically
break once the socket indicated it would block and
to prevent a malicious node from sending replies as
fast as it could - there would be a max message limit
per check period.

Quirks:
* send_line will block until the entire line has been sent even if the socket
  has been set to non-blocking to make things easier. If you need a non-blocking
  way to send a line: use send(). Note that you will have to check for the
  number of bytes sent and resend if needed just like the real send function.
* connect has the same behaviour as above to make things simpler (so will block
  regardless of whether socket is in non-blocking mode or not.) If you want to
  bypass this behaviour you can always connect the socket outside this class
  and then pass it to set_socket.

Otherwise, all functions in this class behave how you would expect them to
(depending on whether you're using non-blocking mode or blocking mode.) It's
assumed that all blocking operations have a timeout by default. This can't be
disabled.

Todo: test various functions under connection exit.
Timeouts are needed for non-blocking too under conditions where you attempt to
send all / recv all.
"""

import errno
import platform
import socket
import ssl
import sys
import time

from pyp2p.lib import get_lan_ip, parse_exception, log_exception
from pyp2p.lib import encode_str

error_log_path = "error.log"


class Sock:
    def __init__(self, addr=None, port=None, blocking=0, timeout=5,
                 interface="default", use_ssl=0, debug=0):
        self.nonce = None
        self.nonce_buf = u""
        self.reply_filter = None
        self.buf = b""
        self.max_buf = 1024 * 1024  # 1 MB.
        self.max_chunks = 1024  # Prevents spamming of multiple short messages.
        self.chunk_size = 1024 * 4
        self.replies = []
        self.blocking = blocking
        self.timeout = timeout
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.use_ssl = use_ssl
        self.alive = time.time()
        self.unl = None
        if self.use_ssl:
            self.s = ssl.wrap_socket(self.s)

        self.connected = 0
        self.interface = interface
        self.delimiter = b"\r\n"
        self.debug = debug

        # Set keep alive.
        # self.set_keep_alive(self.s)

        # Connect socket.
        if addr is not None and port is not None:
            # Set a timeout for blocking operations so they don't DoS program.
            # Disabled after connect if non-blocking is set.
            # (Connect is so far always blocking regardless of blocking mode.)
            self.s.settimeout(5)

            self.connect(addr, port)
        else:
            self.set_blocking(self.blocking, self.timeout)

    def debug_print(self, msg):
        if self.debug:
            msg = "> " + str(msg)
            print(msg)

    def set_keep_alive(self, sock, after_idle_sec=5, interval_sec=60,
                       max_fails=5):
        """
        This function instructs the TCP socket to send a heart beat every n
        seconds to detect dead connections. It's the TCP equivalent of the
        IRC ping-pong protocol and allows for better cleanup / detection
        of dead TCP connections.

        It activates after 1 second (after_idle_sec) of idleness, then sends
        a keepalive ping once every 3 seconds(interval_sec), and closes the
        connection after 5 failed ping (max_fails), or 15 seconds
        """

        # OSX
        if platform.system() == "Darwin":
            # scraped from /usr/include, not exported by python's socket module
            TCP_KEEPALIVE = 0x10
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, TCP_KEEPALIVE, interval_sec)

        if platform.system() == "Windows":
            sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))

        if platform.system() == "Linux":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE,
                            after_idle_sec)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL,
                            interval_sec)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)

    def set_blocking(self, blocking, timeout=5):
        if self.s is None:
            return

        # Update blocking mode.
        self.s.setblocking(blocking)

        # Adjust timeout if needed.
        if blocking:
            if timeout is not None:
                self.s.settimeout(timeout)

        # Update blocking status.
        self.timeout = timeout
        self.blocking = blocking

    def set_sock(self, s):
        self.close()  # Close old socket.
        self.s = s
        self.set_blocking(self.blocking, self.timeout)
        # self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # Set keep alive.
        # self.set_keep_alive(self.s)

        # Save addr + port.
        try:
            addr, port = self.s.getpeername()
            self.addr = addr
            self.port = port
            self.connected = 1
        except:
            self.connected = 0

    def reconnect(self):
        if not self.connected:
            if self.addr is not None and self.port is not None:
                try:
                    return self.connect(self.addr, self.port)
                except:
                    self.connected = 0

    # Blocking (regardless of socket mode.)
    def connect(self, addr, port):
        # Save addr and port so socket can be reconnected.
        self.addr = addr
        self.port = port

        # No socket detected.
        if self.s is None:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if self.use_ssl:
                self.s = ssl.wrap_socket(self.s)

        # Make connection from custom interface.
        if self.interface != "default":
            try:
                # Todo: fix this to use static ips from Net
                src_ip = get_lan_ip(self.interface)
                self.s.bind((src_ip, 0))
            except socket.error as e:
                if e.errno != 98:
                    raise e

        try:
            self.s.connect((addr, int(port)))
            self.connected = 1
            self.set_blocking(self.blocking, self.timeout)
        except Exception as e:
            self.debug_print("Connect failed")
            error = parse_exception(e)
            self.debug_print(error)
            log_exception(error_log_path, error)
            raise socket.error("Socket connect failed.")

    def close(self):
        self.connected = 0

        # Attempt graceful shutdown.
        try:
            try:
                self.s.shutdown(1)
            except:
                pass
            self.s.close()
        except:
            pass

        self.s = None


    def parse_buf(self, encoding="unicode"):
        """
        Since TCP is a stream-orientated protocol, responses aren't guaranteed
        to be complete when they arrive. The buffer stores all the data and
        this function splits the data into replies based on the new line
        delimiter.
        """
        buf_len = len(self.buf)
        replies = []
        reply = b""
        chop = 0
        skip = 0
        i = 0
        buf_len = len(self.buf)
        for i in range(0, buf_len):
            ch = self.buf[i:i + 1]
            if skip:
                skip -= 1
                i += 1
                continue

            nxt = i + 1
            if nxt < buf_len:
                if ch == b"\r" and self.buf[nxt:nxt + 1] == b"\n":

                    # Append new reply.
                    if reply != b"":
                        if encoding == "unicode":
                            replies.append(encode_str(reply, encoding))
                        else:
                            replies.append(reply)
                        reply = b""

                    # Truncate the whole buf if chop is out of bounds.
                    chop = nxt + 1
                    skip = 1
                    i += 1
                    continue

            reply += ch
            i += 1

        # Truncate buf.
        if chop:
            self.buf = self.buf[chop:]

        return replies

    # Blocking or non-blocking.
    def get_chunks(self, fixed_limit=None, encoding="unicode"):
        """
        This is the function which handles retrieving new data chunks. It's
        main logic is avoiding a recv call blocking forever and halting
        the program flow. To do this, it manages errors and keeps an eye
        on the buffer to avoid overflows and DoS attacks.

        http://stackoverflow.com/questions/16745409/what-does-pythons-socket-recv-return-for-non-blocking-sockets-if-no-data-is-r
        http://stackoverflow.com/questions/3187565/select-and-ssl-in-python
        """

        # Socket is disconnected.
        if not self.connected:
            return

        # Recv chunks until network buffer is empty.
        repeat = 1
        wait = 0.2
        chunk_no = 0
        max_buf = self.max_buf
        max_chunks = self.max_chunks
        if fixed_limit is not None:
            max_buf = fixed_limit
            max_chunks = fixed_limit

        while repeat:
            chunk_size = self.chunk_size
            while True:
                # Don't exceed buffer size.
                buf_len = len(self.buf)
                if buf_len >= max_buf:
                    break
                remaining = max_buf - buf_len
                if remaining < chunk_size:
                    chunk_size = remaining

                # Don't allow non-blocking sockets to be
                # DoSed by multiple small replies.
                if chunk_no >= max_chunks and not self.blocking:
                    break

                try:
                    chunk = self.s.recv(chunk_size)
                except socket.timeout as e:
                    self.debug_print("Get chunks timed out.")
                    self.debug_print(e)

                    # Timeout on blocking sockets.
                    err = e.args[0]
                    self.debug_print(err)
                    if err == "timed out":
                        repeat = 0
                        break
                except ssl.SSLError as e:
                    # Will block on non-blocking SSL sockets.
                    if e.errno == ssl.SSL_ERROR_WANT_READ:
                        self.debug_print("SSL_ERROR_WANT_READ")
                        break
                    else:
                        self.debug_print("Get chunks ssl error")
                        self.close()
                        return
                except socket.error as e:
                    # Will block on nonblocking non-SSL sockets.
                    err = e.args[0]
                    if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                        break
                    else:
                        # Connection closed or other problem.
                        self.debug_print("get chunks other closing")
                        self.close()
                        return
                else:
                    if chunk == b"":
                        self.close()
                        return

                    # Avoid decoding errors.
                    self.buf += chunk

                    # Otherwise the loop will be endless.
                    if self.blocking:
                        break

                    # Used to avoid DoS of small packets.
                    chunk_no += 1

            # Repeat is already set -- manual skip.
            if not repeat:
                break
            else:
                repeat = 0

            # Block until there's a full reply or there's a timeout.
            if self.blocking:
                if fixed_limit is None:
                    # Partial response.
                    if self.delimiter not in self.buf:
                        repeat = 1
                        time.sleep(wait)

    def reply_callback(self, callback):
        self.reply_callback = callback

    # Called to check for replies and update buffers.
    def update(self):
        self.get_chunks()
        self.replies += self.parse_buf()

        # Execute callbacks on replies.
        if self.reply_filter is not None:
            replies = []
            for reply in self.replies:
                if not self.reply_filter(reply):
                    replies.append(u"")
                else:
                    replies.append(reply)

            self.replies = replies

    # Blocking or non-blocking.
    def send(self, msg, send_all=0, timeout=5, encoding="ascii"):
        # Update timeout.
        if timeout != self.timeout and self.blocking:
            self.set_blocking(self.blocking, timeout)

        try:
            # Convert to bytes Python 2 & 3
            # The caller should ensure correct encoding.
            if type(msg) == type(u""):
                msg = encode_str(msg, "ascii")

            # Work out stop time.
            if send_all:
                future = time.time() + (timeout or self.timeout)
            else:
                future = 0

            repeat = 1
            total_sent = 0
            msg_len = len(msg)
            while repeat:
                repeat = 0
                while True:
                    # Attempt to send all.
                    # This won't work if the network buffer is already full.
                    try:
                        bytes_sent = self.s.send(
                                msg[total_sent:self.chunk_size])
                    except socket.timeout as e:
                        err = e.args[0]
                        if err == "timed out":
                            return 0
                    except socket.error as e:
                        err = e.args[0]
                        if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                            break
                        else:
                            # Connection closed or other problem.
                            self.debug_print("Con send closing other")
                            self.close()
                            return 0

                    # Connection broken.
                    if not bytes_sent or bytes_sent is None:
                        self.close()
                        return 0

                    # How much has been sent?
                    total_sent += bytes_sent

                    # Avoid looping forever.
                    if self.blocking and not send_all:
                        break

                    # Everything sent.
                    if total_sent >= msg_len:
                        break

                    # Don't block.
                    if not send_all:
                        break

                    # Avoid 100% CPU.
                    time.sleep(0.001)

                # Avoid looping forever.
                if send_all:
                    if time.time() >= future:
                        repeat = 0
                        break

                # Send the rest if blocking:
                if total_sent < msg_len and send_all:
                    repeat = 1

            return total_sent
        except Exception as e:
            self.debug_print("Con send: " + str(e))
            error = parse_exception(e)
            log_exception(error_log_path, error)
            self.close()

    # Blocking or non-blocking.
    def recv(self, n, encoding="unicode", timeout=5):
        # Sanity checking.
        assert n

        # Update timeout.
        if timeout != self.timeout and self.blocking:
            self.set_blocking(self.blocking, timeout)

        try:
            # Get data.
            self.get_chunks(n, encoding=encoding)

            # Return the current buffer.
            ret = self.buf

            # Reset the old buffer.
            self.buf = b""

            # Return results.
            if encoding == "unicode":
                ret = encode_str(ret, encoding)

            return ret
        except Exception as e:
            self.debug_print("Recv closign e" + str(e))
            error = parse_exception(e)
            log_exception(error_log_path, error)
            self.close()
            if encoding == "unicode":
                return u""
            else:
                return b""

    # Sends a new message delimitered by a new line.
    # Blocking: blocks until entire line is sent for simplicity.
    def send_line(self, msg, timeout=5):
        # Sanity checking.
        assert (len(msg))

        # Not connected.
        if not self.connected:
            return 0

        # Update timeout.
        if timeout != self.timeout and self.blocking:
            self.set_blocking(self.blocking, timeout)

        try:
            # Convert to bytes Python 2 & 3
            if type(msg) == type(u""):
                msg = encode_str(msg, "ascii")

            # Convert delimiter to bytes.
            msg += self.delimiter

            """
            The inclusion of the send_all flag makes this function behave like
            a blocking socket for the purposes of sending a full line even if
            the socket is non-blocking. It's assumed that lines will be small
            and if the network buffer is full this code won't end up as a
            bottleneck. (Otherwise you would have to check the number of bytes
            returned every time you sent a line which is quite annoying.)
            """
            ret = self.send(msg, send_all=1, timeout=timeout)

            return ret
        except Exception as e:
            self.debug_print("Send line closing" + str(e))
            error = parse_exception(e)
            log_exception(error_log_path, error)
            self.close()
            return 0

    # Receives a new message delimited by a new line.
    # Blocking or non-blocking.
    def recv_line(self, timeout=5):
        # Socket is disconnected.
        if not self.connected:
            return u""

        # Update timeout.
        if timeout != self.timeout and self.blocking:
            self.set_blocking(self.blocking, timeout)

        # Return existing reply.
        if len(self.replies):
            temp = self.replies[0]
            self.replies = self.replies[1:]
            return temp

        try:
            future = time.time() + (timeout or self.timeout)
            while True:
                self.update()

                # Socket is disconnected.
                if not self.connected:
                    return u""

                # Non-blocking.
                if not ((not len(self.replies) or len(
                        self.buf) >= self.max_buf) and self.blocking):
                    break

                # Timeout elapsed.
                if time.time() >= future and self.blocking:
                    break

                # Avoid 100% CPU.
                time.sleep(0.002)

            if len(self.replies):
                temp = self.replies[0]
                self.replies = self.replies[1:]
                return temp

            return u""
        except Exception as e:
            self.debug_print("recv line error")
            error = parse_exception(e)
            self.debug_print(error)
            log_exception(error_log_path, error)

    """
    These functions here make the class behave like a list. The
    list is a collection of replies received from the socket.
    Every iteration also has the bonus of checking for any
    new replies so it is very easy, for example to do:
    for replies in sock:
        To process replies without handling networking boilerplate.
    """

    def __len__(self):
        self.update()
        return len(self.replies)

    def __getitem__(self, key):
        self.update()
        return self.replies[key]

    def __setitem__(self, key, value):
        self.update()
        self.replies[key] = value

    def __delitem__(self, key):
        self.update()
        del self.replies[key]

    def pop_reply(self):
        # Get replies.
        replies = []
        for reply in self.replies:
            replies.append(reply)

        if len(replies):
            # Put replies back in the queue.
            self.replies = replies[1:]

            # Return the first reply.
            return replies[0]
        else:
            return None

    def __iter__(self):
        try:
            # Get replies.
            self.update()

            # Return replies.
            return iter(self.replies)
        finally:
            # Clear old replies.
            self.replies = []

    def __reversed__(self):
        return self.__iter__()


if __name__ == "__main__":
    """
    s = Sock("158.69.201.105", 8540)

    exit()
    s.send_line("SOURCE TCP")


    while 1:
        for reply in s:
            print(reply)

        time.sleep(0.5)


    # print(s.recv_line())
    # print("yes")
    """
