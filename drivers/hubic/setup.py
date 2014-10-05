from setuptools import setup, find_packages

setup(
    name="onitu-hubic",
    version="0.1",
    url="http://onitu.github.io",
    description="Access your Hubic files with Onitu",
    license="MIT",
    packages=find_packages(),
    install_requires=["requests"],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'hubic = onitu_hubic'
        ],
        'onitu.tests': [
            'hubic = onitu_hubic.tests'
        ]
    }
)
