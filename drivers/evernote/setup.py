from setuptools import setup, find_packages

setup(
    name="onitu-evernote",
    version="0.1",
    url="http://onitu.github.io",
    description="Access your Evernote files with Onitu",
    license="MIT",
    packages=find_packages(),
    install_requires=["evernote"],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'evernote = onitu_evernote'
        ],
        'onitu.tests': [
            'evernote = onitu_evernote.tests'
        ]
    }
)
