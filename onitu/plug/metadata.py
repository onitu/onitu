from onitu.utils import get_fid, get_mimetype, u

from .folder import Folder


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
    **uptodate**
        The entries with an up-to-date version of this file
    **mimetype**
        The MIME type of the file, as detected by python

    Each service can also store extra informations via the :attr:`.extra`
    attribute. It's a dictionary which can contain any kind of information,
    as long as it's JSON serializable.
    Those informations will not be shared with the other entries, as they
    are stocked separately.
    """

    PROPERTIES = ('filename', 'folder_name', 'size', 'uptodate', 'mimetype')

    def __init__(self, plug=None, filename=None, folder=None, folder_name=None,
                 size=0, fid=None, uptodate=None, mimetype=None):
        super(Metadata, self).__init__()

        self.filename = filename
        self.size = size
        self.uptodate = uptodate or ()
        self.mimetype = mimetype

        if folder_name and not folder:
            folder = Folder.get(plug, folder_name)
        elif folder and not folder_name:
            folder_name = folder.name

        self.folder_name = folder_name
        self.folder = folder

        if not fid and filename:
            fid = get_fid(folder_name, filename)
        self.fid = fid

        if not self.mimetype and filename:
            self.mimetype = get_mimetype(filename)

        self.extra = {}

        self.plug = plug

        self._path = None

    @classmethod
    def get(cls, plug, folder, filename):
        """Instantiate a new :class:`.Metadata` object for the file
        with the given name inside the given folder.
        """
        fid = get_fid(folder, filename)
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
            u'file:{}:service:{}'.format(fid, plug.name),
            default={}
        )

        return metadata

    @property
    def path(self):
        if not self._path:
            self._path = self.folder.join(self.filename)

        return self._path

    def dict(self):
        """Return the metadata as a dict"""
        return dict((u(p), getattr(self, p)) for p in self.PROPERTIES)

    def write(self):
        """Write the metadata of the current file in the database."""
        with self.plug.escalator.write_batch() as batch:
            batch.put(
                u'path:{}:{}'.format(self.folder_name, self.filename),
                self.fid
            )
            batch.put('file:{}'.format(self.fid), self.dict())
            batch.put(
                u'file:{}:service:{}'.format(self.fid, self.plug.name),
                self.extra
            )

    def clone(self, new_folder, new_filename):
        """
        Return a new Metadata object with the same properties than the current,
        but with a new filename. The object is not saved in the database, but
        the service's extras are copied and saved.
        """
        values = self.dict()
        values['filename'] = new_filename
        values['folder'] = new_folder
        values['folder_name'] = new_folder.name

        clone = self.__class__(self.plug, **values)

        extras = self.plug.escalator.range('file:{}:service:'.format(self.fid))

        with self.plug.escalator.write_batch() as batch:
            for key, extra in extras:
                service = key.split(':')[-1]
                batch.put(
                    u'file:{}:service:{}'.format(clone.fid, service),
                    extra
                )

        clone.extra = self.extra

        return clone

    def delete(self):
        self.plug.escalator.delete(
            u'file:{}:service:{}'.format(self.fid, self.plug.name),
        )

        other_services = self.plug.escalator.range(
            'file:{}:service:'.format(self.fid), include_value=False
        )
        if not other_services:
            self.plug.escalator.delete('file:{}'.format(self.fid))
            self.plug.escalator.delete(
                u'path:{}:{}'.format(self.folder_name, self.filename)
            )
