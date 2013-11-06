from logbook import error

class Metadata(object):
    """docstring for Metadata"""

    PROPERTIES = {
        'filename': (str, str),
        'size': (int, str),
        'last_update': (float, str),
        'owners': (lambda e: e.split(':'), lambda l: ':'.join(l)),
        'uptodate': (lambda e: e.split(':'), lambda l: ':'.join(l)),
    }

    def __init__(self, filename=None, size=0, last_update=None):
        super(Metadata, self).__init__()

        self.filename = filename
        self.size = size
        self.last_update = last_update

    @classmethod
    def get_by_filename(cls, redis, filename):
        fid = redis.hget('files', filename)

        if fid:
            return cls.get_by_id(redis, fid)
        else:
            return None

    @classmethod
    def get_by_id(cls, redis, fid):
        values = redis.hgetall('files:{}'.format(fid))
        metadata = cls()

        for name, t in cls.PROPERTIES.items():
            metadata.__setattr__(name, t[0](values.get(name)))

        return metadata

    def write(self, redis, fid):
        metadata = {}

        for name, t in self.PROPERTIES.items():
            try:
                metadata[name] = t[1](self.__getattribute__(name))
            except AttributeError as e:
                error("Error writting metadata for {}, missing attribute {}".format(fid, name))
                return

        redis.hmset('files:{}'.format(fid), metadata)
