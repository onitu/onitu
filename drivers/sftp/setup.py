from setuptools import setup, find_packages

setup(
    name="onitu-sftp",
    version="0.1",
    url="http://onitu.github.io",
    description="Store files on a remote machine using SFTP through onitu.",
    license="MIT",
    packages=find_packages(),
    install_requires=["paramiko"],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'sftp = onitu_sftp'
        ],
        'onitu.tests': [
            'sftp = onitu_sftp.tests'
        ]
    }
)
