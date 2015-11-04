from setuptools import setup, find_packages


setup(
    version='0.1',
    description='An open source, Python 2/3, simple p2p library',
    url='http://github.com/robertsdotpm/pyp2p',
    author='Matthew Roberts',
    author_email='matthew@roberts.pm',
    license='MIT',
    packages=find_packages(exclude=('tests','docs')),
    install_requires=[
        'netifaces',
        'ntplib',
        'twisted',
        'ipaddress',
        'requests'
    ]
)


