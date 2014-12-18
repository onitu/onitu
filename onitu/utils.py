"""
This module provides a set of classes and functions useful in several
parts of Onitu.
"""
import os
import sys
import uuid
import string
import signal
import socket
import random
import tempfile
import mimetypes
import traceback
import pkg_resources
import msgpack

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

IS_WINDOWS = os.name == 'nt'

TMPDIR = tempfile.gettempdir()

NAMESPACE_ONITU = uuid.UUID('bcd336f2-d023-4856-bc92-e79dd24b64d7')

UNICODE = unicode if PY2 else str


def b(chars):
    """
    Convert any string (bytes or unicode) to bytes
    """
    if type(chars) == UNICODE:
        return chars.encode('utf-8')
    return chars


def u(chars):
    """
    Convert any chars (bytes or unicode) to unicode
    """
    if type(chars) == bytes:
        return chars.decode('utf-8')
    return chars


def n(string):
    """
    Convert any string (bytes or unicode) to native.
    This is useful to pass it to requests or other modules
    that change behavior when switching py2/py3.
    """
    return (b if PY2 else u)(string)


def pack_obj(obj):
    """
    Encode an unique object with msgpack
    """
    return msgpack.packb(obj, use_bin_type=True)


def pack_msg(*args):
    """
    Encore a message (list of arguments) with msgpack
    """
    return msgpack.packb(args, use_bin_type=True)


def unpack_msg(packed):
    """
    Decode a packed message with msgpack
    """
    return msgpack.unpackb(packed, use_list=False, encoding='utf-8')


def at_exit(callback, *args, **kwargs):
    """
    Register a callback which will be called when a deadly signal comes

    This funtion must be called from the main thread.
    """
    if IS_WINDOWS:
        signals = (signal.SIGILL, signal.SIGABRT, signal.SIGINT,
                   signal.SIGTERM)
    else:
        signals = (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT)

    for s in signals:
        signal.signal(s, lambda *_, **__: callback(*args, **kwargs))


def get_fid(folder, filename):
    """
    Get the file-id (fid) of the given filename inside the given folder.

    The file-id is a UUID version 5, with the namespace define in
    :attr:`NAMESPACE_ONITU`.

    The purpose of the file-id is to avoid using filenames as a direct
    references to files inside Onitu.
    """
    if PY2:
        folder = unicode(folder).encode('utf-8')
        filename = filename.encode('utf-8')

    return str(uuid.uuid5(NAMESPACE_ONITU, "{}:{}".format(folder, filename)))


def get_mimetype(filename):
    """
    Get the MIME type of the given filename.

    This avoids interfaces and clients of the Onitu instances having to
    determine the MIME type of the files they receive notifications from.
    """

    mimetype = mimetypes.guess_type(filename)[0]

    # RFC 2046 states in section 4.5.1:
    # The "octet-stream" subtype is used to indicate that a body contains
    # arbitrary binary data.
    if not mimetype:
        mimetype = 'application/octet-stream'

    return mimetype


def get_random_string(length):
    """
    Return a string containing `length` random alphanumerical chars.
    `length` must be inferior to 62.
    """
    return ''.join(
        random.sample(string.ascii_letters + string.digits, length)
    )

if IS_WINDOWS:
    # We can't use IPC sockets on Windows as they are not supported
    # by ZeroMQ at the moment, so we implement a fallback by creating
    # a temporary file containing an URI corresponding to an open port.
    def _get_uri(session, name):
        sock_file = os.path.join(
            TMPDIR, u'onitu-{}-{}.txt'
        ).format(session, name)

        if os.path.exists(sock_file):
            with open(sock_file) as f:
                return f.read()

        tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmpsock.bind(('127.0.0.1', 0))
        uri = 'tcp://{}:{}'.format(*tmpsock.getsockname())
        tmpsock.close()

        with open(sock_file, 'w+') as f:
            f.write(uri)

        return uri

    def delete_sock_files():
        import glob

        for sock_file in glob.glob(os.path.join(TMPDIR, 'onitu-*.txt')):
            os.unlink(sock_file)
else:
    # On Unix-like systems we use an IPC socket (AF_UNIX)
    def _get_uri(session, name):
        return u'ipc://{}/onitu-{}-{}.sock'.format(TMPDIR, session, name)


def get_escalator_uri(session):
    return _get_uri(session, 'escalator')


def get_events_uri(session, name, suffix=None):
    if suffix:
        name = u"{}:{}".format(name, suffix)

    return _get_uri(session, name)


def get_logs_uri(session):
    return _get_uri(session, 'logs')


def get_circusctl_endpoint(session):
    return _get_uri(session, 'circusctl')


def get_pubsub_endpoint(session):
    return _get_uri(session, 'pubsub')


def get_stats_endpoint(session):
    return _get_uri(session, 'stats')


def get_available_drivers():
    """
    Return a dict mapping the name of each installed driver with its
    entry point.

    You can use it like that:
    ```
    drivers = get_available_drivers()
    if 'local_storage' in drivers:
        local_storage = drivers['local_storage'].load()
    ```
    """
    entry_points = pkg_resources.iter_entry_points('onitu.drivers')
    return {e.name: e for e in entry_points}


def log_traceback(logger=None):
    if logger:
        handler = logger.error
    else:
        from logbook import error

        handler = error

    handler(traceback.format_exc())
