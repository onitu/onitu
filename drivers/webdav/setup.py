from setuptools import setup, find_packages

setup(
    name="onitu-webdav",
    version="0.1",
    url="http://onitu.github.io",
    description="Store files on a remote machine using webdav through onitu.",
    license="MIT",
    packages=find_packages(),
    install_requires=["pycurl", "lxml", "webdavclient"],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'webdav = onitu_webdav'
        ],
        'onitu.tests': [
            'webdav = onitu_webdav.tests'
        ]
    }
)
