import os
import pkg_resources

from .testdriver import TestDriver


class Driver(TestDriver):
    drivers = {}

    def __new__(cls, name, *args, **kwargs):
        entry_points = pkg_resources.iter_entry_points('onitu.tests')
        tests_modules = {e.name: e for e in entry_points}

        if name not in tests_modules:
            raise ImportError(
                "Cannot import tests for driver {}".format(name)
            )

        try:
            tests = tests_modules[name].load()
        except ImportError as e:
            raise ImportError(
                "Error importing tests for driver {}: {}".format(name, e)
            )

        try:
            driver = tests.Driver
        except ImportError:
            raise ImportError(
                "Tests for driver {} don't expose a"
                "Driver class".format(name)
            )

        cls.drivers[name] = driver
        return driver(*args, **kwargs)


class TestingDriver(Driver):
    def __new__(cls, *args, **kwargs):
        return Driver('test', *args, **kwargs)


class TargetDriver(Driver):
    def __new__(cls, *args, **kwargs):
        name = os.environ.get('ONITU_TEST_DRIVER', 'test')
        return Driver(name, *args, **kwargs)
