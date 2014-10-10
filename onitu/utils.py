"""
This module provides a set of classes and functions useful in several
parts of Onitu.
"""
import os
import sys
import uuid
import signal
import socket
import tempfile
import mimetypes
import pkg_resources

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

IS_WINDOWS = os.name == 'nt'

TMPDIR = tempfile.gettempdir()

NAMESPACE_ONITU = uuid.UUID('bcd336f2-d023-4856-bc92-e79dd24b64d7')


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


def get_fid(filename):
    """
    Get the file-id (fid) of the given filename.

    The file-id is a UUID version 5, with the namespace define in
    :attr:`NAMESPACE_ONITU`.

    The purpose of the file-id is to avoid using filenames as a direct
    references to files inside Onitu.
    """
    if PY2:
        filename = filename.encode('utf-8')

    return str(uuid.uuid5(NAMESPACE_ONITU, filename))


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


def get_open_port():
    """
    Return an URI which can be used to bind a socket to an open port.

    The port might be in use between the call to the function and its
    usage, so this function should be used with care.
    """
    tmpsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tmpsock.bind(('127.0.0.1', 0))
    uri = 'tcp://{}:{}'.format(*tmpsock.getsockname())
    tmpsock.close()
    return uri


def get_events_uri(session, escalator, name, suffix=None):
    """
    Return the URI on which a driver or the Referee should be listening
    to in order to get new events.

    On Windows, the URI is stored in the database. If it's not present,
    a valid URI is returned and stored.
    On Unix, a Unix socket is used.
    """
    if suffix:
        name = "{}:{}".format(name, suffix)

    if not IS_WINDOWS:
        return 'ipc://{}/onitu-{}-{}.sock'.format(TMPDIR, session, name)
    else:
        key = 'port:events:{}'.format(name)
        uri = escalator.get(key, default=None)

        if not uri:
            uri = get_open_port()
            escalator.put(key, uri)

        return uri


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
