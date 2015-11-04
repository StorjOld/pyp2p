cd tests
echo "Testing with Python 3."
python3.3 -m "nose" -v test_dht_msg.py
python3.3 -m "nose" -v test_ip_getter.py
python3.3 -m "nose" -v test_nat_pmp.py
python3.3 -m "nose" -v test_net.py
python3.3 -m "nose" -v test_lib.py
python3.3 -m "nose" -v test_rendezvous_client.py
python3.3 -m "nose" -v test_rendezvous_server.py
python3.3 -m "nose" -v test_sock.py
python3.3 -m "nose" -v test_unl.py
python3.3 -m "nose" -v test_upnp.py

echo "Testing with Python 2.7."
python2.7 -m "nose" -v test_dht_msg.py
python2.7 -m "nose" -v test_ip_getter.py
python2.7 -m "nose" -v test_nat_pmp.py
python2.7 -m "nose" -v test_net.py
python2.7 -m "nose" -v test_lib.py
python2.7 -m "nose" -v test_rendezvous_client.py
python2.7 -m "nose" -v test_rendezvous_server.py
python2.7 -m "nose" -v test_sock.py
python2.7 -m "nose" -v test_unl.py
python2.7 -m "nose" -v test_upnp.py
