from onitu.utils import get_fid, get_mimetype, u


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
    **owners**
        The entries which should have this file
    **uptodate**
        The entries with an up-to-date version of this file
    **mimetype**
        The MIME type of the file, as detected by python

    Each entry can also store extra informations via the :attr:`.extra`
    attribute. It's a dictionary which can contain any kind of information,
    as long as it's JSON serializable.
    Those informations will not be shared with the other entries, as they
    are stocked separately.
    """

    PROPERTIES = ('filename', 'size', 'owners', 'uptodate', 'mimetype')

    def __init__(self, plug=None, filename=None, size=0,
                 fid=None, owners=[], uptodate=[], mimetype=None):
        super(Metadata, self).__init__()

        self.filename = filename
        self.size = size
        self.owners = owners
        self.uptodate = uptodate
        self.mimetype = mimetype

        if not fid and filename:
            self.fid = get_fid(filename)
        elif fid:
            self.fid = fid

        if not self.mimetype and filename:
            self.mimetype = get_mimetype(filename)

        self.extra = {}

        self.plug = plug

    @classmethod
    def get_by_filename(cls, plug, filename):
        """Instantiate a new :class:`.Metadata` object for the file
        with the given name.
        """
        fid = get_fid(filename)
        return cls.get_by_id(plug, fid)

    @classmethod
    def get_by_id(cls, plug, fid):
        """Instantiate a new :class:`.Metadata` object for the file
        with the given id.
        """
        values = plug.escalator.get('file:{}'.format(fid), default=None)

        if not values:
            return None

        metadata = cls(plug, fid=fid, **values)

        metadata.extra = plug.escalator.get(
            u'file:{}:entry:{}'.format(fid, plug.name),
            default={}
        )

        return metadata

    def dict(self):
        """Return the metadata as a dict"""
        return dict((p, self.__getattribute__(p)) for p in self.PROPERTIES)

    def write(self):
        """Write the metadata of the current file in the database."""
        with self.plug.escalator.write_batch() as batch:
            batch.put('file:{}'.format(self.fid), self.dict())
            batch.put(
                u'file:{}:entry:{}'.format(self.fid, self.plug.name),
                self.extra
            )

    def clone(self, new_filename):
        """
        Return a new Metadata object with the same properties than the current,
        but with a new filename. The object is not saved in the database, but
        the entry's extras are copied and saved.
        """
        values = self.dict()
        values['filename'] = new_filename

        clone = self.__class__(self.plug, **values)

        extras = self.plug.escalator.range('file:{}:entry:'.format(self.fid))

        with self.plug.escalator.write_batch() as batch:
            for key, extra in extras:
                entry = key.split(':')[-1]
                batch.put(u'file:{}:entry:{}'.format(clone.fid, entry), extra)

        return clone
