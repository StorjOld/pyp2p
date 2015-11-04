from unittest import TestCase
from pyp2p.lib import *
import random

class test_lib(TestCase):
    def test_log_exception(self):
        file_path = "error.log"
        content = "test_log_exception" + str(random.randrange(0, 1231243242343))
        log_exception("error.log", content)
        with open(file_path, "r") as error_log:
            assert(content in error_log.read())

    def test_parse_exception(self):
        try:
            self.this_doesnt_exist()
        except Exception as e:
            assert("AttributeError" in parse_exception(e))

    def test_ip_to_int(self):
        assert(ip2int("127.0.0.1") == 2130706433)

    def test_int_to_ip(self):
        assert(int2ip(2130706433) == "127.0.0.1")

    def test_get_ntp(self):
        ntp = get_ntp()
        assert(type(ntp) == float)
        assert(ntp > 1)

    def test_get_default_gateway(self):
        gw = get_default_gateway()
        assert(gw != None)
        assert(ip2int(gw))
        assert(ip2int(get_default_gateway(u"default")))
        assert(ip2int(get_default_gateway("default")))
        assert(ip2int(get_default_gateway(b"default")))

    def test_get_lan_ip(self):
        lan_ip = get_lan_ip()
        assert(lan_ip != None)
        assert(ip2int(lan_ip))
        assert(ip2int(get_lan_ip("default")))
        assert(ip2int(get_lan_ip(u"default")))
        assert(ip2int(get_lan_ip(b"default")))

    def test_sequential_bind(self):
        mappings = sequential_bind(5)
        assert(mappings != None)
        assert(len(mappings) == 5)

        src_start = mappings[0]["sock"].getsockname()[1]
        index = 0
        for mapping in mappings:
            local_port = mapping["sock"].getsockname()[1]
            assert(local_port == src_start + index)
            mapping["sock"].close()
            index += 1

    def test_is_port_forwarded(self):
        from pyp2p.net import forwarding_servers
        assert(is_port_forwarded(get_lan_ip(), "50031", "TCP", forwarding_servers) == 0)

    def test_is_ip_private(self):
        try:
            assert(is_ip_private(u"192.168.0.400") != 1)
            raise Exception(u"This test should fail.")
        except:
            pass

        assert(is_ip_private(u"127.0.0.1") != 1)
        assert(is_ip_private(u"192.168.0.1"))
        print(is_ip_private(u"8.8.8.8"))
        assert(is_ip_private(u"10.0.0.1"))
        assert(is_ip_private(u"172.16.0.0"))

    def test_is_ip_public(self):
        try:
            assert(is_ip_public(u"dfsdfsdf") != 1)
            raise Exception("These tests should fail.")
        except:
            pass

        try:
            assert(is_ip_public(u"www.example.com") != 1)
            raise Exception("These tests should fail.")
        except:
            pass

        try:
            assert(is_ip_public(u"127.0.0.1") != 1)
            raise Exception("These tests should fail.")
        except:
            pass

        assert(is_ip_public(u"192.168.0.1") != 1)
        assert(is_ip_public(u"8.8.8.8"))

    def test_is_ip_valid(self):
        assert(is_ip_valid(b"127.0.0.1"))
        assert(is_ip_valid(b"10.0.0.1"))
        assert(is_ip_valid(b"8.8.8.8"))
        assert(is_ip_valid(b"0.0.0.0"))
        assert(is_ip_valid(b"127.0.0.400") != 1)
        assert(is_ip_valid(b"192.168.0.1"))
        assert(is_ip_valid(b"127.0.0.0.1") != 1)
        assert(is_ip_valid(b"127.0.0.256") != 1)
        assert(is_ip_valid(b"localhost") != 1)
        assert(is_ip_valid(b"any") != 1)
        assert(is_ip_valid(b"255.255.255.255"))
        assert(is_ip_valid(get_lan_ip()))
        assert(is_ip_valid(get_wan_ip()))
        assert(is_ip_valid("127.0.0.1"))
        assert(is_ip_valid("10.0.0.1"))
        assert(is_ip_valid("8.8.8.8"))
        assert(is_ip_valid("0.0.0.0"))
        assert(is_ip_valid("127.0.0.400") != 1)
        assert(is_ip_valid("192.168.0.1"))
        assert(is_ip_valid("127.0.0.0.1") != 1)
        assert(is_ip_valid("127.0.0.256") != 1)
        assert(is_ip_valid("localhost") != 1)
        assert(is_ip_valid("any") != 1)
        assert(is_ip_valid("255.255.255.255"))
        assert(is_ip_valid(get_lan_ip()))
        assert(is_ip_valid(get_wan_ip()))
        assert(is_ip_valid(u"127.0.0.1"))
        assert(is_ip_valid(u"10.0.0.1"))
        assert(is_ip_valid(u"8.8.8.8"))
        assert(is_ip_valid(u"0.0.0.0"))
        assert(is_ip_valid(u"127.0.0.400") != 1)
        assert(is_ip_valid(u"192.168.0.1"))
        assert(is_ip_valid(u"127.0.0.0.1") != 1)
        assert(is_ip_valid(u"127.0.0.256") != 1)
        assert(is_ip_valid(u"localhost") != 1)
        assert(is_ip_valid(u"any") != 1)
        assert(is_ip_valid(u"255.255.255.255"))
        assert(is_ip_valid(get_lan_ip()))
        assert(is_ip_valid(get_wan_ip()))

    def test_is_valid_port(self):
        assert(is_valid_port("1"))
        assert(is_valid_port("65535"))
        assert(is_valid_port("0") != 1)
        assert(is_valid_port("-500") != 1)
        assert(is_valid_port("-100") != 1)
        assert(is_valid_port("65536") != 1)
        assert(is_valid_port("test") != 1)

    def test_get_wan_ip(self):
        assert(is_ip_valid(get_wan_ip()))
