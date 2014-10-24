from setuptools import setup, find_packages

setup(
    name="onitu-test-driver",
    version="0.1",
    url="http://onitu.github.io",
    description="Driver used to test Onitu."
                "Should not be used outside the tests.",
    license="MIT",
    packages=find_packages(),
    install_requires=[],
    package_data={'': ['manifest.json']},
    entry_points={
        'onitu.drivers': [
            'test = onitu_test_driver'
        ],
        'onitu.tests': [
            'test = onitu_test_driver.tests'
        ]
    }
)
