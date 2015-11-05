# Make sure to also increment version #.
sudo python2.7 setup.py sdist
sudo python2.7 setup.py bdist_wheel
sudo python2.7 setup.py sdist bdist_wheel upload
