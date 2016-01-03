cd tests
echo "Testing with Python 3."
python3.3 -m "nose" -v test_dht_msg.py
python3.3 -m "nose" -v test_nat_pmp.py
python3.3 -m "nose" -v test_net.py
python3.3 -m "nose" -v test_lib.py
python3.3 -m "nose" -v test_rendezvous_client.py
python3.3 -m "nose" -v test_rendezvous_server.py
python3.3 -m "nose" -v test_sock.py
python3.3 -m "nose" -v test_unl.py
python3.3 -m "nose" -v test_upnp.py
python3.3 -m "nose" -v test_hybrid_reply.py