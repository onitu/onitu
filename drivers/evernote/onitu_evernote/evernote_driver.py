import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.type.ttypes as Types

from datetime import timedelta
from evernote.edam.error.ttypes import EDAMUserException, EDAMSystemException
from evernote.edam.error.ttypes import EDAMErrorCode
from evernote.api.client import EvernoteClient
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.edam.type.ttypes import NoteSortOrder

import threading
import hashlib
import os
import binascii
import time
import datetime

from path import path

from onitu.plug import Plug, ServiceError

root = None
changes_timer = None
onitu_recent_search = None
onitu_search = None
notebook_onitu = None
plug = Plug()

# ############################## EVERNOTE ####################################


def connect_client():
    global note_store

    plug.logger.debug("Connecting to Evernote")
    try:
        client = EvernoteClient(token=plug.options['token'])
        note_store = client.get_note_store()
    except (EDAMUserException, EDAMSystemException) as e:
        raise ServiceError(
            "Cannot connect to Evernote: {}".format(e)
            )


def create_notebook(name):
    plug.logger.debug("Creating notebook {}".format(name))
    return note_store.createNotebook(plug.options['token'],
                                     Types.Notebook(name=name))


def create_root_notebook():
    """Creates the notebook named by the Onitu root if it doesn't already exist
    We take care of stripping the slashes before and after"""
    # Clean the root before trying to create the Onitu notebook
    global root
    root = plug.options['root']
    if root.startswith('/'):
        root = root[1:]
    if root.endswith('/'):
        root = root[:-1]
    global notebook_onitu
    try:
        notebook_onitu = create_notebook(root)
    except EDAMUserException as eue:
        # DATA_CONFLICT "Notebook.name" = name already in use
        # We want to create the notebook if it doesn't already exist
        # So in our case this is ok, raise the error otherwise
        if not (eue.errorCode == EDAMErrorCode.DATA_CONFLICT
                and eue.parameter == "Notebook.name"):
            raise ServiceError("Error creating '{}' notebook: {}", root, eue)
        else:
            plug.logger.debug("Notebook {} already exists".format(root))
            for n in note_store.listNotebooks():
                if n.name == root:
                    plug.logger.debug("Found {} notebook".format(root))
                    notebook_onitu = n
                    break
            # If the given notebook has been said existing BUT we can't find it
            # For example if it has been deleted between when we asked and
            # when we retrieved the list... In this case trying again will
            # create it the next time.
            if notebook_onitu is None:
                raise ServiceError("Couldn't fetch notebook {}, "
                                   "please try again".format(root))


def create_note(metadata, content):
    ''' Return the note created which contains its guid'''
    global note_store

    filename = '{}/{}'.format(root, '/', metadata.filename)
    filename = metadata.filename
    note_title = filename

    note = Types.Note()
    note.title = note_title
    global notebook_onitu
    note.notebookGuid = notebook_onitu.guid

    # To include an attachment such as an image in a note, first create a Resource
    # for the attachment. At a minimum, the Resource contains the binary attachment
    # data, an MD5 hash of the binary data, and the attachment MIME type.
    # It can also include attributes such as filename and location.
    md5 = hashlib.md5()
    md5.update(content)
    md5_hash = md5.digest()

    data = Types.Data()
    data.size = len(content)
    data.bodyHash = md5_hash
    data.body = content

    attr = Types.ResourceAttributes()
    attr.fileName = filename

    resource = Types.Resource()
    resource.mime = metadata.mimetype
    resource.data = data
    resource.attributes = attr

    note.resources = [resource]

    hash_hex = binascii.hexlify(md5_hash)

    # The content of an Evernote note is represented using Evernote Markup Language
    # (ENML). The full ENML specification can be found in the Evernote API Overview
    # at http://dev.evernote.com/documentation/cloud/chapters/ENML.php
    note.content = '<?xml version="1.0" encoding="UTF-8"?>'
    note.content += '<!DOCTYPE en-note SYSTEM ' \
        '"http://xml.evernote.com/pub/enml2.dtd">'
    note.content += '<en-note>This note was created by onitu to store your '
    note.content += metadata.filename + ' file.<br/><br/>'
    note.content += '<en-media type="' + metadata.mimetype + '" hash="' + hash_hex + '"/>'
    note.content += '</en-note>'

    return note_store.createNote(note)


# ############################# ONITU HANDLERS ###################################

#Unexpected error calling 'move_file': 'str' object has no attribute 'write' ?
# with updateresource we cannot update the content, only metadata
@plug.handler()
def move_file(old_metadata, new_metadata):
    global note_store
    global dev_token

    note = note_store.getNote(dev_token, old_metadata.extra['guid'], False, False, True, False)

    res = note.resources[0] #Types.Resource()
    attr = Types.ResourceAttributes()
    attr.fileName = new_metadata.filename
    print
    print "MOVE: New filename =" + attr.fileName
    print

#    res.guid = note.resources[0].guid
    res.attributes = attr
    res.mime = new_metadata.mimetype
    note_store.updateResource(dev_token, res)

@plug.handler()
def get_file(metadata):
    note = note_store.getNote(dev_token, metadata.extra['guid'], False, False, False, True)
    return note_store.getResourceData(dev_token, note.resources[0].guid)

@plug.handler()
def upload_file(metadata, content):
    note = create_note(metadata, content)
    metadata.extra['guid'] = note.guid
    metadata.extra['revision'] = note.updated / 1000
    metadata.write()

@plug.handler()
def delete_file(metadata):
    res = note_store.deleteNote(dev_token, metadata.extra['guid'])

# ############################## WATCHER ######################################


class CheckChanges(threading.Thread):
    """A class spawned in a thread to poll for changes on the HUBIC bucket.
    HUBIC hasn't any bucket watching system in its API, so the best we can
    do is periodically polling the bucket's contents and compare the
    timestamps."""

    def __init__(self, root, timer):
        threading.Thread.__init__(self)
        self.stop = threading.Event()
        self.timer = timer
        self.root = root
        self.last_check = 0
        self.basic_filters = "notebook:{} resource:*".format(notebook_onitu.name)

        escalator = plug.escalator
        try:
            self.last_check = escalator.get('evernote_last_check')
            self.first_start = False
        except KeyError:
            self.first_start = True
            self.last_check = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            escalator.put('evernote_last_check', self.last_check)

        client = EvernoteClient(token=dev_token)
        self.note_store = client.get_note_store()

    def check_changes(self):
        self.check_updated()
        self.check_deleted()
        self.first_start = False

        self.last_check = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        escalator = plug.escalator
        escalator.put('evernote_last_check', self.last_check)

    def check_deleted(self):
        escalator = plug.escalator

        # The field that we want in the response
        result_spec = NotesMetadataResultSpec()
        result_spec.includeDeleted = True
        result_spec.includeTitle = True

        note_deleted = NoteFilter(order=NoteSortOrder.UPDATED, inactive=True)
        note_deleted.inactive = True
        note_deleted.words = self.basic_filters

        if self.first_start is False:
            note_deleted.words += " deleted:{}".format(self.last_check)

        page_size = 200
        i = 0
        while 42:
            res = self.note_store.findNotesMetadata(dev_token, note_deleted, i, page_size, result_spec)
            for n in res.notes:
                try:
                    res_guid = escalator.get('note_guid:{}'.format(n.guid))
                except KeyError:
                    res_guid = None

                if res_guid is None:
                    note = self.note_store.getNote(dev_token, n.guid, False, True, False, False)
                    res_guid = note.resources[0].guid  # Only one resource per note

                resource = self.note_store.getResource(dev_token, res_guid, False, False, True, False)
                filename = resource.attributes.fileName

                metadata = plug.get_metadata(filename)
                print "DELETE REVIEW OF FILE "+ filename + " --- Title= " + n.title

                if n.deleted is not None:
                    plug.delete_file(metadata)
                    print
                    print "DELETE FILE " + filename + " ---- Title= " + n.title
                    print

            # update the range that we want or break iff there is no more notes
            if (res.totalNotes == 0) or (i + len(res.notes) >= res.totalNotes):
                break
            i = i + page_size

    def check_updated(self):
        escalator = plug.escalator

        result_spec = NotesMetadataResultSpec()
        result_spec.includeCreated = True
        result_spec.includeUpdated = True
        result_spec.includeTitle = True

        note_updated = NoteFilter(order=NoteSortOrder.UPDATED, inactive=False)
        note_updated.words = self.basic_filters
        if self.first_start is False:
            note_updated.words += " updated:{}".format(self.last_check)

        page_size = 200
        i = 0
        while 42:
            res = self.note_store.findNotesMetadata(dev_token, note_updated, i, page_size, result_spec)
            for n in res.notes:
                try:
                    res_guid = escalator.get('note_guid:{}'.format(n.guid))
                except KeyError:
                    res_guid = None

                if res_guid is None:
                    note = self.note_store.getNote(dev_token, n.guid, False, True, False, False)
                    res_guid = note.resources[0].guid  # Only one resource per note

                resource = self.note_store.getResource(dev_token, res_guid, False, False, True, False)
                filename = resource.attributes.fileName

                metadata = plug.get_metadata(filename)
                onitu_rev = metadata.extra.get('revision', 0.)
                print "REVIEW OF FILE " + filename + " --- Title= " + n.title

                # n.updated contains miliseconds
                if (n.updated / 1000) > onitu_rev:
                    print
                    print "DOWNLOAD " + filename + " --- Title= " + n.title
                    print
                    escalator.put('note_guid:{}'.format(n.guid), res_guid)
                    metadata.extra['revision'] = (n.updated / 1000)
                    metadata.extra['guid'] = n.guid
                    metadata.size = resource.data.size
                    metadata.write()
                    plug.update_file(metadata)

            # update the range that we want or break iff there is no more notes
            if (res.totalNotes == 0) or (i + len(res.notes) >= res.totalNotes):
                break
            i = i + page_size

    def run(self):
        while not self.stop.isSet():
            self.check_changes()
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    global changes_timer
    changes_timer = plug.options['changes_timer']
    if changes_timer < 0:
        raise DriverError("Changes timer must be a positive value")

    # Start the Evernote connection and retrieve our note store
    connect_client()
    plug.logger.debug("Connection successful")
    # Try to create the onitu notebook
    create_root_notebook()

    # Launch the changes detection
    check = CheckChanges(root, plug.options['changes_timer'])
    check.daemon = True
    check.start()

    plug.listen()