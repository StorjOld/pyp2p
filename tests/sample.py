
from pyp2p.lib import *
from pyp2p.dht_msg import DHT
from pyp2p.net import Net
import random
from threading import Thread
import time
import logging
from pyp2p.sock import Sock

import random
import os
import tempfile
import hashlib
if sys.version_info >= (3, 0, 0):
    from urllib.parse import urlparse
else:
    from urlparse import urlparse

from pyp2p.unl import UNL
import pyp2p

success_no = 0
found_con = 0
test_no_1_success = 1

print(pyp2p.lib.get_lan_ip())

