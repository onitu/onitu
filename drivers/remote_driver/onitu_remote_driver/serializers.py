from onitu.plug.folder import Folder

def metadata_serializer(m):
    props = [getattr(m, p) for p in m.PROPERTIES]
    return m.fid, props, m.extra


def metadata_unserialize(plug, m):
    fid, props, extra = m
    filename = props[0]
    metadata = plug.get_metadata(filename)
    if metadata is None:
        return None
    for name, prop in zip(metadata.PROPERTIES, props):
        setattr(metadata, name, prop)
    metadata.extra = extra
    return metadata

def folder_serializer(f):
    return f.name, f.path, f.options

def folder_unserialize(plug, f):
    return Folder(*f)

serializers = {
    'metadata': metadata_serializer,
    'folder': folder_serializer,
}
