import argparse
import re

if re.match("^pyp2p", __name__) != None:
    # Setup parser.
    parser = argparse.ArgumentParser(prog='pyp2p')

    # Option: LAN IP.
    parser.add_argument('-lan_ip', '--lan_ip', action="store", dest="lan_ip", help="query string", default=None)

    # Option: LAN IP.
    parser.add_argument('-wan_ip', '--wan_ip', action="store", dest="wan_ip", help="query string", default=None)

    # Parse arguments.
    args = args, unknown = parser.parse_known_args()
else:
    class Args():
        def __init__(self):
            self.wan_ip = None
            self.lan_ip = None

    args = Args()
