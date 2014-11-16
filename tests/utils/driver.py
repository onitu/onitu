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

    def close(self):
        pass

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


class DriverFeatures(object):
    copy_file_from_onitu = True
    copy_file_to_onitu = True
    del_file_from_onitu = True
    del_file_to_onitu = True
    move_file_from_onitu = True
    move_file_to_onitu = True

    copy_directory_from_onitu = True
    copy_directory_to_onitu = True
    del_directory_from_onitu = True
    del_directory_to_onitu = True
    move_directory_from_onitu = True
    move_directory_to_onitu = True

    copy_tree_from_onitu = True
    copy_tree_to_onitu = True
    del_tree_from_onitu = True
    del_tree_to_onitu = True
    move_tree_from_onitu = True
    move_tree_to_onitu = True

    detect_new_file_on_launch = True
    detect_del_file_on_launch = True
    detect_moved_file_on_launch = True


_loaded_drivers_cache = {}


def load_driver_module(name):
    module = _loaded_drivers_cache.get(name)
    if module is not None:
        return module
    try:
        entry_point = next(iter(pkg_resources.iter_entry_points('onitu.tests',
                                                                name)))
        module = entry_point.load()
        _loaded_drivers_cache[name] = module
        return module
    except StopIteration:
        raise ImportError("Cannot import tests for driver {}".format(name))
    except Exception as e:
        raise ImportError("Error importing tests for driver {}: "
                          "{}: {}".format(name, type(e).__name__, e))


def load_driver(name):
    module = load_driver_module(name)
    try:
        return module.Driver, module.DriverFeatures
    except Exception as e:
        raise ImportError("Error importing tests for driver {}: "
                          "{}: {}".format(name, type(e).__name__, e))
