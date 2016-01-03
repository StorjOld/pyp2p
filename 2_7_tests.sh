cd tests
echo "Testing with Python 2.7."
python2.7 -m "nose" -v test_dht_msg.py
python2.7 -m "nose" -v test_nat_pmp.py
python2.7 -m "nose" -v test_net.py
python2.7 -m "nose" -v test_lib.py
python2.7 -m "nose" -v test_rendezvous_client.py
python2.7 -m "nose" -v test_rendezvous_server.py
python2.7 -m "nose" -v test_sock.py
python2.7 -m "nose" -v test_unl.py
python2.7 -m "nose" -v test_upnp.py
python2.7 -m "nose" -v test_hybrid_reply.py