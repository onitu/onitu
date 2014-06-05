"""
This module provides a set of classes and functions useful in several
parts of Onitu.
"""
import sys
import uuid
import tempfile

PY2 = sys.version_info[0] == 2
PY3 = sys.version_info[0] == 3

TMPDIR = tempfile.gettempdir()

NAMESPACE_ONITU = uuid.UUID('bcd336f2-d023-4856-bc92-e79dd24b64d7')


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


def get_escalator_uri(session):
    """
    Return the URI on which Escalator should be listening for
    the given session.
    """
    return 'ipc://{}/onitu-{}-escalator.sock'.format(TMPDIR, session)


def get_events_uri(session, name):
    """
    Return the URI on which a driver or the Referee should be listening
    to in order to get new events.
    """
    return 'ipc://{}/onitu-{}-events-{}.sock'.format(TMPDIR, session, name)
