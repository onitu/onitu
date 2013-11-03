class Metadata(object):
    """docstring for Metadata"""

    PROPERTIES = {
        'filename': str,
        'size': int,
        'last_update': float,
        'owners': lambda e: e.split(':'),
        'uptodate': lambda e: e.split(':')
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

        for name, f in cls.PROPERTIES.items():
            metadata.__setattr__(name, f(values.get(name)))

        return metadata

    def write(self, redis, fid):
        metadata = {}

        for name in self.PROPERTIES.keys():
            try:
                metadata[name] = str(self.__getattribute__(name))
            except AttributeError as e:
                print("Error writting metadata for {}, missing attribute {}".format(fid, name))
                return

        redis.hmset('files:{}'.format(fid), metadata)
