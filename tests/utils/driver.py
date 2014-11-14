import re
import pkg_resources


class Driver(object):

    SPEED_BUMP = 0
    """
    Can be used by fast drivers (like LocalStorage) to slow down
    some tests.

    The value is the chunk_size which will be used in the tests
    requiring slow-downs. If 0, no speed-bumps are used (default).
    """

    def __init__(self, type, name=None, speed_bump=False, **options):
        self.type = type
        self.name = name if name else type
        self.options = options

        if speed_bump and self.SPEED_BUMP > 0:
            self.options['chunk_size'] = self.SPEED_BUMP

    @property
    def slugname(self):
        return re.sub(r'__+', '_', re.sub(r'[^a-z0-9]', '_',
                                          self.name.lower()))

    @property
    def dump(self):
        return {'driver': self.type, 'options': self.options}

    @property
    def id(self):
        return (self.type, self.name)

    def connect(self, session):
        pass

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


def load_driver(name):
    try:
        entry_point = next(iter(pkg_resources.iter_entry_points('onitu.tests',
                                                                name)))
        return entry_point.load().Driver
    except StopIteration:
        raise ImportError("Cannot import tests for driver {}".format(name))
    except Exception as e:
        raise ImportError("Error importing tests for driver {}:"
                          "{}: {}".format(name, type(e).__name__, e))
