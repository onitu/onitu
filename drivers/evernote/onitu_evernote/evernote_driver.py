import threading
import hashlib
import os
import binascii
import time
import datetime
from datetime import timedelta
from path import path
from httplib import ResponseNotReady

import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.type.ttypes as Types
from evernote.edam.error.ttypes import EDAMUserException, EDAMSystemException
from evernote.edam.error.ttypes import EDAMNotFoundException, EDAMErrorCode
from evernote.api.client import EvernoteClient
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.edam.notestore.ttypes import SyncState, SyncChunkFilter
from evernote.edam.type.ttypes import NoteSortOrder
from evernote.edam.limits.constants import EDAM_USER_NOTES_MAX

import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import thrift.transport.THttpClient as THttpClient

from onitu.plug import Plug, DriverError, ServiceError
from onitu.utils import u,b

root = None
token = None
changes_timer = None
onitu_recent_search = None
onitu_search = None
notestore_onitu = None
notebook_onitu = None
plug = Plug()

# ############################## EVERNOTE ####################################

def update_resource_metadata(onituMetadata, resource):
    """Updates the Onitu metadata of a resource file. Quite not the same thing
    as updating a note."""
    # Data may not be set so be careful
    if hasattr(resource, "data"):
        onituMetadata.size = resource.data.size
    onituMetadata.extra['evernote_guid'] = resource.guid
    # noteGuid helps us to remember if a file is a file's resource or not
    onituMetadata.extra['evernote_note_guid'] = resource.noteGuid
    onituMetadata.extra['evernote_USN'] = resource.updateSequenceNum
    plug.update_file(onituMetadata)


def update_note_metadata(onituMetadata, note, updateFile=False):
    """Updates the Onitu metadata of an Evernote note. If updateFile is True,
    call plug.update_file. If not, just call metadata.write"""
    onituMetadata.size = note.contentLength
    onituMetadata.extra['evernote_guid'] = note.guid
    onituMetadata.extra['evernote_hash'] = note.contentHash
    onituMetadata.extra['evernote_USN'] = note.updateSequenceNum
    # Usually this function gets called if an update has been detected, but
    # we must call plug.update_file only if it's a content-related change.
    # Yet we have to update ourseslves about the USN, for example.
    if updateFile:
        plug.update_file(onituMetadata)
    else:
        onituMetadata.write()


def connect_client():
    global notestore_onitu
    global token
    plug.logger.debug("Connecting to Evernote...")
    token = b(plug.options['token'])
    try:
        client = EvernoteClient(token=token)
        notestore_onitu = client.get_note_store()
    except (EDAMUserException, EDAMSystemException) as e:
        raise ServiceError(
            "Cannot connect to Evernote: {}".format(e)
        )
    plug.logger.debug("Connection successful")


def create_notebook(name):
    plug.logger.debug(u"Creating notebook {}".format(name))
    return notestore_onitu.createNotebook(token,
                                     Types.Notebook(name=name))


def create_root_notebook():
    """Creates the notebook named by the Onitu root if it doesn't already exist
    We take care of stripping the slashes before and after"""
    # Clean the root before trying to create the Onitu notebook
    global root
    root = u(plug.options['root'])
    if root.startswith(u'/'):
        root = root[1:]
    if root.endswith(u'/'):
        root = root[:-1]
    global notebook_onitu
    for n in notestore_onitu.listNotebooks():
        if n.name == root:
            plug.logger.debug(u"Found {} notebook".format(root))
            notebook_onitu = n
            break
    # The notebook does not exist: create it
    if notebook_onitu is None:
        try:
            notebook_onitu = create_notebook(root)
        except (EDAMUserException, EDAMSystemException) as exc:
            raise ServiceError(u"Error creating '{}' notebook: {}", root, exc)

def create_note(metadata, content):
    """ Return the note created which contains its guid"""
    global notestore_onitu

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

    return notestore_onitu.createNote(note)


# ############################# ONITU HANDLERS ###################################

#Unexpected error calling 'move_file': 'str' object has no attribute 'write' ?
# with updateresource we cannot update the content, only metadata
@plug.handler()
def move_file(old_metadata, new_metadata):
    global notestore_onitu
    global dev_token

    note = notestore_onitu.getNote(dev_token, old_metadata.extra['guid'], False, False, True, False)

    res = note.resources[0] #Types.Resource()
    attr = Types.ResourceAttributes()
    attr.fileName = new_metadata.filename
    print
    print "MOVE: New filename =" + attr.fileName
    print

#    res.guid = note.resources[0].guid
    res.attributes = attr
    res.mime = new_metadata.mimetype
    notestore_onitu.updateResource(dev_token, res)


@plug.handler()
def get_file(metadata):
    # We MUST have a guid when working with Evernote files
    guid = metadata.extra.get('evernote_guid', None)
    if guid is None:
        raise DriverError(u"No GUID for file '{}'!".format(metadata.filename))
    # We must use a different API call if the file is actually a resource !
    noteGuid = metadata.extra.get('evernote_note_guid', None)
    data = ''
    try:
        if noteGuid is None:  # The file is a note
            # Only request the note content
            data = notestore_onitu.getNoteContent(guid)
        else:  # The file is a note's resource
            data = notestore_onitu.getResourceData(guid)
    except (EDAMUserException, EDAMSystemException,
            EDAMNotFoundException) as exc:
        raise ServiceError(u"Could not get file {}: {}"
                           .format(metadata.filename, exc))
    return data


@plug.handler()
def upload_file(metadata, content):
    note = create_note(metadata, content)
    metadata.extra['guid'] = note.guid
    metadata.extra['revision'] = note.updated / 1000
    metadata.write()

@plug.handler()
def delete_file(metadata):
    res = notestore_onitu.deleteNote(dev_token, metadata.extra['guid'])


# ############################## WATCHER ######################################

class CheckChanges(threading.Thread):
    """A class spawned in a thread to poll for changes on the Evernote notebook
    Evernote lets us know if we're up-to-date with a sync state number. Once we
    see our number doesn't match anymore the server's one, we start an
    update."""

    def __init__(self, root, timer):
        threading.Thread.__init__(self)
        self.stop = threading.Event()
        self.timer = timer
        self.root = root
        # The last update count of the notebook we're aware of.
        #         self.updateCount = plug.entry_db.get('notebook_USN', default=0)
        self.notebookUSN = 0
        # We don't want to paginate. Ask all teh notes in one time
        self.maxNotes = EDAM_USER_NOTES_MAX
        # Filter to include only notes from our notebook
        self.noteFilter = NoteFilter(order=NoteSortOrder.RELEVANCE,
                                     notebookGuid=notebook_onitu.guid)
        # Note spec to filter even more the findNotesMetadata result
        self.resultSpec = NotesMetadataResultSpec(includeTitle=True, 
                                                  includeContentLength=True,
                                                  includeCreated=True,
                                                  includeUpdated=True,
                                                  includeDeleted=True,
                                                  includeUpdateSequenceNum=True)
        self.first_start = True
        self.note_store = notestore_onitu


    def update_note(self, noteMetadata, onituMetadata):
        """Update a given note's information, content and also its
        resource files. We come to this function when we already know the
        server copy is more recent than ours.
        But to ensure it is a change of content, we store the hash, and we
        compare the current with the one we stored when a file gets updated."""
        # First just check the hash
        plug.logger.debug(u"Getting content hash of {}"
                          .format(noteMetadata.title))
        # Get the resource data as well
        note = notestore_onitu.getNote(noteMetadata.guid, False, True, False,
                                       False)
        onituHash = onituMetadata.extra.get('evernote_hash', "")
        updateFile = False
        # The content hash changed: notify an update
        if note.contentHash != onituHash:
            updateFile = True
            plug.logger.debug(u"Note {} updated".format(note.title))
        update_note_metadata(onituMetadata, note, updateFile=updateFile)
        if not updateFile:
            plug.logger.debug(u"Update on note {} isn't content-related, "
                              u"I update the metadata but won't call "
                              u"plug.update_file".format(note.title))
        # Check the resources now
        for resource in note.resources:
            # TODO: File names could change! Find a way to manage that...
            # Maybe an entry_db field keeping track of all the files that
            # are actually resources ?
            plug.logger.debug(u"Processing note {}'s resource {}"
                              .format(note.title, resource.attributes.fileName))
            resourceMetadata = plug.get_metadata(resource.attributes.fileName)
            onitu_USN = resourceMetadata.extra.get('evernote_USN', 0)
            # Nothing fancy about the resources: if the USN changed,
            # re-download it
            if onitu_USN < resource.updateSequenceNum:
                update_resource_metadata(resourceMetadata, resource)

    def check_changes(self):
        """The function that will check the notes in the notebook are uptodate.
        Evernote doesn't let us check regular and deleted files at the same
        time, so we have to do two separate passes."""
        plug.logger.debug("CHECKONS!")
        self.check_updated()

        plug.logger.debug("Done checking changes")

 #       self.check_deleted()



    def check_updated(self):
        """Checks for updated notes on the Onitu notebook.
        Loops the findNotesMetadata operation until everything is gone."""
        remaining = 1
        offset = 0
        while remaining:
            # Ask as much notes as possible in one shot
            res = notestore_onitu.findNotesMetadata(self.noteFilter, offset,
                                                    self.maxNotes,
                                                    self.resultSpec)
            plug.logger.debug("{}".format(res.totalNotes))
            # In spite of one could think, res.notes actually are Evernote
            # NoteMetadata, not Note instances...
            for noteMetadata in res.notes:
                # The note content and its resources are in a specific folder
                onituMetadata = plug.get_metadata(noteMetadata.title)
                # Update Sequence Num is like a kind of operation counter.
                # If it is higher than what we had, something new happened.
                # The flaw in this logic is that it can have nothing to do with
                # the logic Onitu is interested in, e.g. the note has a new tag
                # AFAIK there is no better solution right now.
                usn = noteMetadata.updateSequenceNum
                onitu_usn = onituMetadata.extra.get('evernote_USN', 0)
                if onitu_usn < usn:
                    try:
                        self.update_note(noteMetadata, onituMetadata)
                    except (EDAMUserException, EDAMSystemException,
                            EDAMNotFoundException) as exc:
                        plug.logger.error(u"Couldn't update note {}: {}"
                                          .format(noteMetadata.title, exc))
                else:
                    plug.logger.debug(u"Note {} is up-to-date"
                                      .format(noteMetadata.title))
            # Update the offset to ask the rest of the notes next time
            offset = res.startIndex + len(res.notes)
            remaining = res.totalNotes - offset
        # dev_token = plug.options['token']
        # result_spec = NotesMetadataResultSpec()
        # result_spec.includeCreated = True
        # result_spec.includeUpdated = True
        # result_spec.includeTitle = True

        # note_updated = NoteFilter(order=NoteSortOrder.UPDATED, inactive=False)
        # note_updated.words = self.basic_filters
        # if self.first_start is False:
        #     note_updated.words += " updated:{}".format(self.last_check)

        # page_size = 200
        # i = 0
        # while 42:
        #     res = self.note_store.findNotesMetadata(dev_token, note_updated, i, page_size, result_spec)
        #     for n in res.notes:
        #         try:
        #             res_guid = escalator.get('note_guid:{}'.format(n.guid))
        #         except KeyError:
        #             res_guid = None

        #         if res_guid is None:
        #             note = self.note_store.getNote(dev_token, n.guid, False, True, False, False)
        #             res_guid = note.resources[0].guid  # Only one resource per note

        #         resource = self.note_store.getResource(dev_token, res_guid, False, False, True, False)
        #         filename = resource.attributes.fileName

        #         metadata = plug.get_metadata(filename)
        #         onitu_rev = metadata.extra.get('revision', 0.)
        #         print "REVIEW OF FILE " + filename + " --- Title= " + n.title

        #         # n.updated contains miliseconds
        #         if (n.updated / 1000) > onitu_rev:
        #             print
        #             print "DOWNLOAD " + filename + " --- Title= " + n.title
        #             print
        #             escalator.put('note_guid:{}'.format(n.guid), res_guid)
        #             metadata.extra['revision'] = (n.updated / 1000)
        #             metadata.extra['guid'] = n.guid
        #             metadata.size = resource.data.size
        #             metadata.write()
        #             plug.update_file(metadata)

        #     # update the range that we want or break iff there is no more notes
        #     if (res.totalNotes == 0) or (i + len(res.notes) >= res.totalNotes):
        #         break
        #     i = i + page_size


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

    def run(self):
        while not self.stop.isSet():
            try:
                # Let's see if we're up-to-date
                # Update the notebook Onitu watches
                global notebook_onitu
                notebook_onitu = notestore_onitu.getNotebook(
                    notebook_onitu.guid)
                # There has been a new transaction on the notebook
                if self.notebookUSN < notebook_onitu.updateSequenceNum:
                    plug.logger.debug("Notebook USN {} is more recent than "
                                      "mine ({}), updating myself"
                                      .format(notebook_onitu.updateSequenceNum,
                                              self.notebookUSN))
                    self.check_changes()
                    # Update ourselves
                    self.notebookUSN = notebook_onitu.updateSequenceNum
                    plug.entry_db.put('notebook_USN',
                                      notebook_onitu.updateSequenceNum)
                else:
                    plug.logger.debug("I'm up to date")
            except (EDAMUserException, EDAMSystemException) as exc:
                raise ServiceError("Error while polling Evernote changes: {}"
                                   .format(exc))
            except ResponseNotReady:
                plug.logger.warning("Cannot poll changes because notebook data"
                                    "isn't ready. Will retry later...")
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
    # Try to create the onitu notebook
    create_root_notebook()

    # Launch the changes detection
    check = CheckChanges(root, plug.options['changes_timer'])
    check.daemon = True
    check.start()

    plug.listen()
