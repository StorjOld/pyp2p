from unittest import TestCase
from pyp2p.lib import *
from pyp2p.rendezvous_client import *
import random

# if sys.version_info >= (3,0,0):


class test_rendezvous_client(TestCase):
    def test_00001(self):
        from pyp2p.net import rendezvous_servers
        client = RendezvousClient(nat_type="preserving",
                                  rendezvous_servers=rendezvous_servers)

        # attend_fight (Not tested)

        ret = client.sequential_connect()
        assert(ret != None)
        ret[0].close()

        assert(client.simultaneous_listen())

        assert(client.passive_listen(45673))

        assert(client.leave_fight())

        # throw_punch (Not tested)
        # simultaneous_fight (Not tested)

        # simultaneous_challenge (Not tested)

        assert(client.parse_remote_port("REMOTE TCP 50000") == 50000)
        assert(client.parse_remote_port(u"REMOTE TCP 50000") == 50000)

        mappings = [\
            {
                "remote": 100
            },
            {
                "remote": 200
            },
            {
                "remote": 300
            },
            {
                "remote": 400
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == 100)
        assert(ret["nat_type"] == "delta")

        mappings = [\
            {
                "remote": 100
            },
            {
                "remote": 300
            },
            {
                "remote": 300
            },
            {
                "remote": 400
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == 100)
        assert(ret["nat_type"] == "delta")

        mappings = [\
            {
                "remote": 100
            },
            {
                "remote": 300
            },
            {
                "remote": 300
            },
            {
                "remote": 300
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == 0)
        assert(ret["nat_type"] == "random")


        mappings = [\
            {
                "remote": 1
            },
            {
                "remote": 2
            },
            {
                "remote": 3
            },
            {
                "remote": 4
            },
            {
                "remote": 5
            },
            {
                "remote": 6
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == 1)
        assert(ret["nat_type"] == "delta")


        mappings = [\
            {
                "remote": 1
            },
            {
                "remote": 3
            },
            {
                "remote": 3
            },
            {
                "remote": 4
            },
            {
                "remote": 5
            },
            {
                "remote": 6
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == 1)
        assert(ret["nat_type"] == "delta")


        mappings = [\
            {
                "remote": 6
            },
            {
                "remote": 5
            },
            {
                "remote": 4
            },
            {
                "remote": 3
            },
            {
                "remote": 2
            },
            {
                "remote": 1
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == -1)
        assert(ret["nat_type"] == "delta")


        mappings = [\
            {
                "remote": 6
            },
            {
                "remote": 6
            },
            {
                "remote": 5
            },
            {
                "remote": 3
            },
            {
                "remote": 2
            },
            {
                "remote": 1
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == -1)
        assert(ret["nat_type"] == "delta")

        mappings = [\
            {
                "remote": 600
            },
            {
                "remote": 550
            },
            {
                "remote": 500
            },
            {
                "remote": 450
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == -50)
        assert(ret["nat_type"] == "delta")

        mappings = [\
            {
                "remote": 600
            },
            {
                "remote": 1000
            },
            {
                "remote": 500
            },
            {
                "remote": 450
            }
        ]

        ret = client.delta_test(mappings)
        assert(ret["delta"] == -50)
        assert(ret["nat_type"] == "delta")

        mappings = [\
            {
                "remote": 1000
            },
            {
                "remote": 2000
            },
            {
                "remote": 500
            },
            {
                "remote": 3000
            },
            {
                "remote": 4000
            }
        ]

        ret = client.delta_test(mappings)
        print(ret)
        assert(ret["delta"] == 1000)
        assert(ret["nat_type"] == "delta")

        assert(client.determine_nat() != "unknown")