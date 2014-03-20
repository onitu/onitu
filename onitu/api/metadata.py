class Metadata(object):
    """The Metadata class represent the metadata of any file in Onitu.

    This class should always be instantiated via the
    :meth:`.get_by_id` or :meth:`.get_by_filename`
    class methods.
    However, the drivers should never instantiate a new
    :class:`.Metadata` object themselves, but use the
    :meth:`.Plug.get_metadata` function.

    The attributes available for each file are the following :

    **filename**
        The absolute filename of the file
    **size**
        The size of the file, in octets
    **revision**
        This field is specific to each entry. It is a string
        representing the current revision of the file for the
        current entry.
        The drivers should compare an upstream and a local version
        of a file with this field. The format is dependant from the
        driver (it can be whatever you want: a timestamp, a number,
        a hash...).
    **owners**
        The entries which should have this file
    **uptodate**
        The entries with an up-to-date version of this file
    """

    PROPERTIES = {
        'filename': (str, str),
        'size': (int, str),
        'owners': (lambda e: e.split(':'), lambda l: ':'.join(l)),
        'uptodate': (lambda e: e.split(':'), lambda l: ':'.join(l)),
    }

    def __init__(self, plug=None, filename=None, size=0):
        super(Metadata, self).__init__()

        self.filename = filename
        self.size = size

        self.plug = plug
        self.session = plug.session

        self._revision = None
        self._fid = None

    @classmethod
    def get_by_filename(cls, plug, filename):
        """Instantiate a new :class:`.Metadata` object for the file
        with the given name.
        """
        fid = plug.session.hget('files', filename)

        if fid:
            return cls.get_by_id(plug, fid)
        else:
            return None

    @classmethod
    def get_by_id(cls, plug, fid):
        """Instantiate a new :class:`.Metadata` object for the file
        with the given id.
        """
        values = plug.session.hgetall('files:{}'.format(fid))

        if not values:
            return None

        metadata = cls(plug)
        metadata._fid = fid

        for name, (deserialize, _) in cls.PROPERTIES.items():
            metadata.__setattr__(name, deserialize(values.get(name)))

        return metadata

    @property
    def revision(self):
        """The revision of a file can be any string, and should be
        used to compare the different versions of a file on driver.

        Each driver can use its own system of revisions, as it is
        stored for each entry.
        """
        if self._revision:
            return self._revision
        elif self._fid:
            return self.session.hget(
                'drivers:{}:files'.format(self.plug.name),
                self._fid
            )

    @revision.setter
    def revision(self, value):
        self._revision = value

    def write_revision(self):
        """Write the current revision in the database. Called
        by :meth:`.write`.
        """
        if not self._revision:
            return

        self.session.hset(
            'drivers:{}:files'.format(self.plug.name),
            self._fid,
            self._revision
        )

        self._revision = None

    def write(self):
        """Write the metadata of the current file in the database.
        """
        metadata = {}

        for name, (_, serialize) in self.PROPERTIES.items():
            try:
                metadata[name] = serialize(self.__getattribute__(name))
            except AttributeError:
                self.plug.logger.error(
                    "Error writing metadata for {}, missing attribute {}",
                    self._fid, name
                )
                return

        self.session.hmset('files:{}'.format(self._fid), metadata)

        self.write_revision()
