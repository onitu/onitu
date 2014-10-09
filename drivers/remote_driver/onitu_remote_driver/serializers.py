def metadata_serializer(m):
    props = [getattr(m, p) for p in m.PROPERTIES]
    return m.fid, props, m.extra


def metadata_unserialize(plug, m):
    fid, (filename, size, owners, uptodate), extra = m
    metadata = plug.get_metadata(filename)
    metadata.size = size
    metadata.owners = owners
    metadata.uptodate = uptodate
    metadata.extra = extra
    return metadata

serializers = {
    'metadata': metadata_serializer
}
