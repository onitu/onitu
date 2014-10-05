from setuptools import setup, find_packages

setup(
    name="onitu-dropbox",
    version="0.1",
    url="http://onitu.github.io",
    description="Access your Dropbox files with Onitu",
    license="MIT",
    packages=find_packages(),
    install_requires=["dropbox"],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'dropbox = onitu_dropbox'
        ],
        'onitu.tests': [
            'dropbox = onitu_dropbox.tests'
        ]
    }
)
