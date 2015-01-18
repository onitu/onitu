from onitu.utils import pack_msg
from .folder import FolderWrapper

class MetadataWrapper(object):
    PROPERTIES = ('filename', 'folder_name', 'size', 'uptodate', 'mimetype')

    def __init__(self, plug, fid, props, extra):
        self.plug = plug
        self.fid = fid
        for name, value in zip(self.PROPERTIES, props):
            setattr(self, name, value)
        self.folder = FolderWrapper.get(plug, self.folder_name)
        self._path = None
        self.extra = extra

    def write(self):
        self.plug.logger.debug('metadata:write {}', self.filename)
        self.plug.request(pack_msg('metadata_write',
                                   metadata_serializer(self)))

    @property
    def path(self):
        if not self._path:
            self._path = self.folder.join(self.filename)
        return self._path

def metadata_serializer(m):
    props = [getattr(m, p) for p in m.PROPERTIES]
    return m.fid, props, m.extra
