from setuptools import setup, find_packages

setup(
    name="onitu-amazon-s3",
    version="0.1",
    url="http://onitu.github.io",
    description="Access your Amazon S3 buckets with Onitu",
    license="MIT",
    packages=find_packages(),
    install_requires=["requests"],
    dependency_links=[
        "git+git://github.com/Scylardor/tinys3#egg=tinys3"
    ],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'amazon_s3 = onitu_amazon_s3'
        ],
        'onitu.tests': [
            'amazon_s3 = onitu_amazon_s3.tests'
        ]
    }
)
