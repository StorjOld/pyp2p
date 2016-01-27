#!/usr/bin/env python
"""
This module is designed to fetch your external IP address from the internet.
It is used mostly when behind a NAT.
It picks your IP randomly from a serverlist to minimize request
overhead on a single server

If you want to add or remove your server from the list contact me on github


API Usage
=========

    >>> import ipgetter
    >>> myip = ipgetter.myip()
    >>> myip
    '8.8.8.8'

    >>> ipgetter.IPgetter().test()

    Number of servers: 47
    IP's :
    8.8.8.8 = 47 ocurrencies


Copyright 2014 phoemur@gmail.com
This work is free. You can redistribute it and/or modify it under the
terms of the Do What The Fuck You Want To Public License, Version 2,
as published by Sam Hocevar. See http://www.wtfpl.net/ for more details.
"""

import re
import random
import socket
from threading import Timer

from sys import version_info

import future.moves.urllib.request
urllib = future.moves.urllib.request
PY3K = version_info >= (3, 0)

__version__ = "0.6"


def myip():
    return IPgetter().get_external_ip()


class IPgetter(object):

    """
    This class is designed to fetch your external IP address from the internet.
    It is used mostly when behind a NAT.
    It picks your IP randomly from a serverlist to minimize request overhead
    on a single server
    """

    def __init__(self):
        self.server_list = ['http://ip.dnsexit.com',
                            'http://ifconfig.me/ip',
                            'http://ipecho.net/plain',
                            'http://checkip.dyndns.org/plain',
                            'http://ipogre.com/linux.php',
                            'http://whatismyipaddress.com/',
                            'http://ip.my-proxy.com/',
                            'http://websiteipaddress.com/WhatIsMyIp',
                            'http://getmyipaddress.org/',
                            'http://www.my-ip-address.net/',
                            'http://myexternalip.com/raw',
                            'http://www.canyouseeme.org/',
                            'http://www.trackip.net/',
                            'http://icanhazip.com/',
                            'http://www.iplocation.net/',
                            'http://www.howtofindmyipaddress.com/',
                            'http://www.ipchicken.com/',
                            'http://whatsmyip.net/',
                            'http://www.ip-adress.com/',
                            'http://checkmyip.com/',
                            'http://www.tracemyip.org/',
                            'http://checkmyip.net/',
                            'http://www.lawrencegoetz.com/programs/ipinfo/',
                            'http://www.findmyip.co/',
                            'http://ip-lookup.net/',
                            'http://www.dslreports.com/whois',
                            'http://www.mon-ip.com/en/my-ip/',
                            'http://www.myip.ru',
                            'http://ipgoat.com/',
                            'http://www.myipnumber.com/my-ip-address.asp',
                            'http://www.whatsmyipaddress.net/',
                            'http://formyip.com/',
                            'https://check.torproject.org/',
                            'http://www.displaymyip.com/',
                            'http://www.bobborst.com/tools/whatsmyip/',
                            'http://www.geoiptool.com/',
                            'https://www.whatsmydns.net/whats-my-ip-address.html',
                            'https://www.privateinternetaccess.com/pages/whats-my-ip/',
                            'http://checkip.dyndns.com/',
                            'http://myexternalip.com/',
                            'http://www.ip-adress.eu/',
                            'http://www.infosniper.net/',
                            'http://wtfismyip.com/',
                            'http://ipinfo.io/',
                            'http://httpbin.org/ip']

        self.timeout = 1.6
        self.url = None

    def get_external_ip(self):
        """
        This function gets your IP from a random server
        """

        random.shuffle(self.server_list)
        myip = ''
        for server in self.server_list[:3]:
            myip = self.fetch(server)
            if myip != '':
                return myip
            else:
                continue
        return ''

    def handle_timeout(self, url):
        if self.url is not None:
            self.url.close()
            self.url = None

    def fetch(self, server):
        """
        This function gets your IP from a specific server
        """
        t = None
        socket_default_timeout = socket.getdefaulttimeout()
        opener = urllib.build_opener()
        opener.addheaders = [('User-agent',
                              "Mozilla/5.0 (X11; Linux x86_64; rv:24.0)"
                              " Gecko/20100101 Firefox/24.0")]

        try:
            # Close url resource if fetching not finished within timeout.
            t = Timer(self.timeout, self.handle_timeout, [self.url])
            t.start()

            # Open URL.
            if version_info[0:2] == (2, 5):
                # Support for Python 2.5.* using socket hack
                # (Changes global socket timeout.)
                socket.setdefaulttimeout(self.timeout)
                self.url = opener.open(server)
            else:
                self.url = opener.open(server, timeout=self.timeout)
    
            # Read response.
            content = self.url.read()

            # Didn't want to import chardet. Prefered to stick to stdlib
            if PY3K:
                try:
                    content = content.decode('UTF-8')
                except UnicodeDecodeError:
                    content = content.decode('ISO-8859-1')

            p = '(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.('
            p += '25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|['
            p += '01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)'
            m = re.search(
                p,
                content)
            myip = m.group(0)
            if len(myip) > 0:
                return myip
            else:
                return ''
        except Exception as e:
            print(e)
            return ''
        finally:
            if self.url is not None:
                self.url.close()
                self.url = None
            if t is not None:
                t.cancel()

            # Reset default socket timeout.
            if socket.getdefaulttimeout() != socket_default_timeout:
                socket.setdefaulttimeout(socket_default_timeout)

    def test(self):
        """
        This functions tests the consistency of the servers
        on the list when retrieving your IP.
        All results should be the same.
        """

        resultdict = {}
        for server in self.server_list:
            resultdict.update(**{server: self.fetch(server)})

        ips = sorted(resultdict.values())
        ips_set = set(ips)
        print('\nNumber of servers: {}'.format(len(self.server_list)))
        print("IP's :")
        for ip, ocorrencia in zip(ips_set, map(lambda x: ips.count(x), ips_set)):
            print('{0} = {1} ocurrenc{2}'.format(ip if len(ip) > 0 else 'broken server', ocorrencia, 'y' if ocorrencia == 1 else 'ies'))
        print('\n')
        print(resultdict)

if __name__ == '__main__':
    print(myip())
