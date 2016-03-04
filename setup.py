from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    version='0.8.1',
    name='pyp2p',
    description='Python P2P networking library',
    keywords=('NAT traversal, TCP hole punching, simultaneous open, UPnP,'
              ' NATPMP, P2P, Peer-to-peer networking library, python'),
    long_description=long_description,
    url='http://github.com/Storj/pyp2p',
    author='Storj',
    author_email='matthew@storj.io',
    test_suite="tests",
    license='MIT',
    packages=find_packages(exclude=('tests', 'docs')),
    install_requires=[
        'netifaces>=0.10.4',
        'ntplib>=0.3.3',
        'twisted>=15.4.0',
        'ipaddress>=1.0.14',
        'requests>=2.8.1',
        'pyroute2>=0.3.15'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
    ],
)
