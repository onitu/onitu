import os
from importlib import import_module

from .testdriver import TestDriver


class Driver(TestDriver):
    drivers = {}

    def __new__(cls, type, *args, **kwargs):
        if not type in cls.drivers:
            try:
                mod = import_module('onitu.drivers.{}.tests.driver'.
                                    format(type))
            except ImportError:
                raise KeyError("No such driver '{}'".format(repr(type)))
            cls.drivers[type] = mod.Driver
        return cls.drivers[type](*args, **kwargs)


class LocalStorageDriver(TestDriver):
    def __new__(cls, *args, **kwargs):
        return Driver('local_storage', *args, **kwargs)


class TargetDriver(Driver):
    def __new__(cls, *args, **kwargs):
        type = os.environ.get('ONITU_TEST_DRIVER', 'local_storage')
        return Driver(type, *args, **kwargs)
