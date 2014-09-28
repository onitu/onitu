import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.type.ttypes as Types

from datetime import timedelta
from evernote.edam.error.ttypes import EDAMUserException
from evernote.api.client import EvernoteClient
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.edam.type.ttypes import NoteSortOrder

import cStringIO
import threading
import requests
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
dev_token = None
plug = Plug()

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

        escalator = plug.escalator
        try:
            self.last_check = escalator.get('evernote_last_check')
            print "LAST check found " + str(self.last_check)
            self.first_start = False
        except KeyError:
            self.first_start = True
            self.last_check = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            escalator.put('evernote_last_check', self.last_check)
            print "LAST check not found"

        client = EvernoteClient(token=dev_token)
        self.note_store = client.get_note_store()

    def check_changes(self):
        dt = datetime.datetime.strptime(self.last_check, "%Y%m%dT%H%M%SZ")
        dt -= timedelta(seconds=self.timer)
        check_time = dt.strftime("%Y%m%dT%H%M%SZ")
        check_time = self.last_check 

        self.last_check = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        escalator = plug.escalator
        escalator.put('evernote_last_check', self.last_check)


        onitu_nb = " notebook:" + notebook_onitu.name
        resource = " resource:*"
        updated = " updated:" + check_time

        node_filter = NoteFilter(order=NoteSortOrder.UPDATED)
        node_filter.words = onitu_nb + resource

        if self.first_start is False:
            node_filter.words += updated
        else:
            self.first_start = False

        result_spec = NotesMetadataResultSpec()
        result_spec.includeCreated = True
        result_spec.includeUpdated = True
        result_spec.includeDeleted = True
        result_spec.includeTitle = True

        page_size = 200
        i = 0
        while 42:
            res = self.note_store.findNotesMetadata(dev_token, node_filter, i, page_size, result_spec)
            print res
            for n in res.notes:
                try:
                    res_guid = escalator.get('note_guid:{}'.format(n.guid))
                    print "ID found in escalator"
                except KeyError:
                    res_guid = None

                if res_guid is None:
                    note = self.note_store.getNote(dev_token, n.guid, False, True, False, False)
                    res_guid = None
                    for r in note.resources:
                        res_guid = r.guid
                        break

                resource = self.note_store.getResource(dev_token, res_guid, False, False, True, False)
                filename = resource.attributes.fileName

                metadata = plug.get_metadata(filename)
                onitu_rev = metadata.extra.get('revision', 0.)

                print filename
                '''print n.title
                print filename
                print n.updated
                print onitu_rev'''
                #n.updated contains miliseconds
                if (n.updated / 1000) > onitu_rev:
#                    metadata.size = 700#resource.alternateData.size
                    escalator.put('note_guid:{}'.format(n.guid), res_guid)
                    metadata.extra['revision'] = (n.updated / 1000)
                    metadata.extra['guid'] = n.guid
                    metadata.write()
                    plug.update_file(metadata)

            if (res.totalNotes == 0) or (i + len(res.notes) >= res.totalNotes):
                break
            i = i + page_size

    def run(self):
        while not self.stop.isSet():
            self.check_changes()
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()

# ############################## EVERNOTE ####################################

def create_note(metadata, content):
    ''' Return the note created which contains its guid'''
    global note_store

    note_title = metadata.filename

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
    attr.fileName = metadata.filename

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

# ############################# ONITU BASIC ###################################

#Unexpected error calling 'move_file': 'str' object has no attribute 'write' ?
@plug.handler()
def move_file(old_metadata, new_metadata):
    global note_store
    global dev_token

    note = note_store.getNote(dev_token, old_metadata.extra['guid'], False, False, True, False)

    for r in note.resources:
        resource = Types.Resource()
        attr = Types.ResourceAttributes()
        resource.mime = new_metadata.mimetype
        attr.fileName = new_metadata.filename
        res = note_store.updateResource(dev_token, r.guid)
        break


@plug.handler()
def get_file(metadata):
    note = note_store.getNote(dev_token, metadata.extra['guid'], False, False, False, True)

    for r in note.resources:
        content = note_store.getResourceData(dev_token, r.guid)
        return content

@plug.handler()
def upload_file(metadata, content):
    filename = root + '/' + metadata.filename

    note = create_note(metadata, content)
    metadata.extra['guid'] = note.guid
    metadata.extra['revision'] = note.updated / 1000
    metadata.write()

@plug.handler()
def delete_file(metadata):
    res = note_store.deleteNote(dev_token, metadata.extra['guid'])

def create_notebook(name):
    notebook = Types.Notebook()
    notebook.name = name
    return note_store.createNotebook(dev_token, notebook)

def create_main_notebook(name):
    try:
        return create_notebook(name)
    except EDAMUserException:
        '''
        BAD_DATA_FORMAT "Notebook.name" - invalid length or pattern
        BAD_DATA_FORMAT "Notebook.stack" - invalid length or pattern
        BAD_DATA_FORMAT "Publishing.uri" - if publishing set but bad uri
        BAD_DATA_FORMAT "Publishing.publicDescription" - if too long
        DATA_CONFLICT "Notebook.name" - name already in use
        DATA_CONFLICT "Publishing.uri" - if URI already in use
        DATA_REQUIRED "Publishing.uri" - if publishing set but uri missing
        LIMIT_REACHED "Notebook" - at max number of notebooks
        '''
        global note_store
        notebooks = note_store.listNotebooks()
        for n in notebooks:
            if (n.name == name):
                return n

def start():
    global plug

    global changes_timer
    changes_timer = plug.options['changes_timer']

    # Clean the root
    global root
    root = plug.options['root']
    if root.startswith('/'):
        root = root[1:]
    if root.endswith('/'):
        root = root[:-1]

    global dev_token
    dev_token = ""
    client = EvernoteClient(token=dev_token)
    global note_store
    note_store = client.get_note_store()

    # Try to create the onitu notebook
    global notebook_onitu
    notebook_onitu = create_main_notebook(root)

    #    fill_searches()
    # Launch the changes detection
    check = CheckChanges(root, plug.options['changes_timer'])
    check.daemon = True
    check.start()

    plug.listen()
