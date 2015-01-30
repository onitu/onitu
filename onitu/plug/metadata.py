import time

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
    **mimetype**
        The MIME type of the file, as detected by python

    Each service can also store extra informations via the :attr:`.extra`
    attribute. It's a dictionary which can contain any kind of information,
    as long as it's JSON serializable.
    Those informations will not be shared with the other entries, as they
    are stocked separately.
    """

    PROPERTIES = ('filename', 'folder_name', 'size', 'mimetype')

    def __init__(self, plug=None, filename=None, folder=None, folder_name=None,
                 size=0, fid=None, mimetype=None):
        super(Metadata, self).__init__()

        self._filename = None
        self._folder_name = None
        self._size = None

        self.filename = filename
        self.size = size
        self.mimetype = mimetype

        if folder_name and not folder:
            folder = Folder.get(plug, folder_name)
        elif folder and not folder_name:
            folder_name = folder.name

        self.folder_name = folder_name
        self.folder = folder

        if not fid and self.filename:
            fid = get_fid(self.folder_name, self.filename)
        self.fid = fid

        if not self.mimetype and self.filename:
            self.mimetype = get_mimetype(self.filename)

        self.extra = {}

        self.plug = plug

        self._path = None

    @classmethod
    def get(cls, plug, folder, filename):
        """Instantiate a new :class:`.Metadata` object for the file
        with the given name inside the given folder.
        """
        fid = get_fid(folder, u(filename))
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
    def filename(self):
        return self._filename

    @filename.setter
    def filename(self, value):
        if value is None:
            self._filename = None
        else:
            self._filename = u(value)

    @property
    def folder_name(self):
        return self._folder_name

    @folder_name.setter
    def folder_name(self, value):
        if value is None:
            self._folder_name = None
        else:
            self._folder_name = u(value)

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        if value is None:
            self._size = None
        else:
            self._size = int(value)

    @property
    def path(self):
        if not self._path:
            self._path = self.folder.join(self.filename)

        return self._path

    @property
    def is_uptodate(self):
        return self.plug.escalator.exists(
            u'file:{}:uptodate:{}'.format(self.fid, self.plug.name)
        )

    @property
    def last_update(self):
        """
        Return the timestamp of the last update for this service if the
        file is up-to-date, and `None` otherwise.
        """
        return self.plug.escalator.get(
            u'file:{}:uptodate:{}'.format(self.fid, self.plug.name),
            default=None
        )

    @property
    def uptodate_services(self):
        services = self.plug.escalator.range(
            'file:{}:uptodate:'.format(self.fid), include_value=False
        )
        return tuple(key.split(':')[-1] for key in services)

    def set_uptodate(self, reset=False):
        if reset:
            services = self.plug.escalator.range(
                'file:{}:uptodate:'.format(self.fid), include_value=False
            )
            for key in services:
                self.plug.escalator.delete(key)

        self.plug.escalator.put(
            u'file:{}:uptodate:{}'.format(self.fid, self.plug.name),
            time.time()
        )

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
