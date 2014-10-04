from setuptools import setup, find_packages

from onitu import __version__

with open('README.rst') as f:
    readme = f.read()

setup(
    name="onitu",
    version=__version__,
    url='http://onitu.github.io',
    description="Sync and share your files from various services and backends",
    author="Onitu Epitech Innovative Project",
    author_email="onitu_2015@labeip.epitech.eu",
    license="MIT",
    long_description=readme,
    packages=find_packages(exclude=['drivers', 'tests', 'docs']),
    install_requires=[
        "circus>=0.11",
        "pyzmq>=14.1.1",
        "logbook>=0.7",
        "plyvel",
        "msgpack-python",
        "bottle"
    ],
    extras_require={
        'dev': ['flake8', 'sphinx', 'tox'],
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
