from setuptools import setup, find_packages

setup(
    name="onitu-google-drive",
    version="0.1",
    url="http://onitu.github.io",
    description="Access your Google Drive files with Onitu",
    license="MIT",
    packages=find_packages(),
    install_requires=["requests"],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'google_drive = onitu_google_drive'
        ],
        'onitu.tests': [
            'google_drive = onitu_google_drive.tests'
        ]
    }
)
