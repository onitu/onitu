from setuptools import setup, find_packages

setup(
    name="onitu-remote-driver",
    version="0.1",
    url="http://onitu.github.io",
    description="Launch a driver on a remote computer",
    license="MIT",
    packages=find_packages(),
    install_requires=[],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'remote_driver = onitu_remote_driver'
        ],
        'onitu.tests': [
            'remote_driver = onitu_remote_driver.tests'
        ]
    }
)
