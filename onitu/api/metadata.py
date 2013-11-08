from logbook import error

class Metadata(object):
    """The Metadata class represent the metadata of any file in Onitu.

    This class should be instantiated via the `get_by_id` or
    `get_by_filename` class methods.

    The PROPERTIES class property represent each property found in the
    metadata common to all drivers. This is a dict where the key is the
    name of the property and the item is a tuple containing two
    functions, one which should be applied the metadata are extracted
    from Redis, the other one they are written.
    """

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
        """Instantiate a new Metadata object for the file with the
        given name.
        """
        fid = redis.hget('files', filename)

        if fid:
            return cls.get_by_id(redis, fid)
        else:
            return None

    @classmethod
    def get_by_id(cls, redis, fid):
        """Instantiate a new Metadata object for the file with the
        given id.
        """
        values = redis.hgetall('files:{}'.format(fid))
        metadata = cls()

        for name, (deserialize, _) in cls.PROPERTIES.items():
            metadata.__setattr__(name, deserialize(values.get(name)))

        return metadata

    def write(self, redis, fid):
        """Write the metadata for the current object in Redis.
        """
        metadata = {}

        for name, (_, serialize) in self.PROPERTIES.items():
            try:
                metadata[name] = serialize(self.__getattribute__(name))
            except AttributeError:
                error("Error writing metadata for {}, missing attribute {}"
                        .format(fid, name))
                return

        redis.hmset('files:{}'.format(fid), metadata)
