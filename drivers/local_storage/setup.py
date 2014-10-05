import sys
from setuptools import setup, find_packages

install_requires = ["path.py"]

if sys.platform.startswith('linux'):
    install_requires.append('pyinotify')
elif sys.platform.startswith('win'):
    install_requires.append('pywin32')

setup(
    name="onitu-local-storage",
    version="0.1",
    url="http://onitu.github.io",
    description="Access your local files with Onitu",
    license="MIT",
    packages=find_packages(),
    install_requires=install_requires,
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'local_storage = onitu_local_storage'
        ],
        'onitu.tests': [
            'local_storage = onitu_local_storage.tests'
        ]
    }
)
