import re


class TestDriver(object):
    def __init__(self, type, name=None, **options):
        self.type = type
        self.name = name if name else type
        self.options = options

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

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id
