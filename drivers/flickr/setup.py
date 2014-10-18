from setuptools import setup, find_packages

setup(
    name="onitu-flickr",
    version="0.1",
    url="http://onitu.github.io",
    description="Synchronize onitu with your flickr account",
    license="MIT",
    packages=find_packages(),
    install_requires=["requests", "requests_toolbelt", "requests_oauthlib"],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'flickr = onitu_flickr'
        ]
    }
)
