import sys

from setuptools import setup, find_packages

import onitu

with open('README.rst') as f:
    readme = f.read()


requirements = [
    "circus>=0.11",
    "pyzmq>=14.1.1",
    "logbook>=0.7",
    "plyvel",
    "pyyaml",
    "msgpack-python",
    "bottle"
]

if sys.version_info[0] == 2:
    requirements.append('futures')

setup(
    name="onitu",
    version=onitu.__version__,
    url='http://onitu.github.io',
    description=onitu.__doc__,
    author=onitu.__author__,
    author_email=onitu.__email__,
    license=onitu.__license__,
    long_description=readme,
    packages=find_packages(exclude=['drivers', 'tests', 'docs']),
    zip_safe=False,
    install_requires=requirements,
    extras_require={
        'dev': ['flake8', 'tox'],
        'doc': ['sphinx', 'sphinxcontrib-httpdomain'],
        'tests': ['pytest', 'requests'],
        'bench': ['codespeed-client']
    },
    entry_points={
        'console_scripts': [
            'onitu = onitu.__main__:main'
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Customer Service",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Other Audience",
        "Intended Audience :: System Administrators",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: Communications :: File Sharing",
        "Topic :: Internet",
        "Topic :: Multimedia",
        "Topic :: Office/Business",
        "Topic :: Utilities",
    ],
    keywords='onitu sync sharing',
)
