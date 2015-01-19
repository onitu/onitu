import threading
import hashlib
from httplib import ResponseNotReady

import evernote.edam.type.ttypes as Types
from evernote.edam.error.ttypes import EDAMUserException, EDAMSystemException
from evernote.edam.error.ttypes import EDAMNotFoundException
from evernote.api.client import EvernoteClient
from evernote.edam.notestore.ttypes import NoteFilter, NotesMetadataResultSpec
from evernote.edam.type.ttypes import NoteSortOrder
from evernote.edam.limits.constants import EDAM_USER_NOTES_MAX

from onitu.plug import Plug, DriverError, ServiceError
from onitu.escalator.client import EscalatorClosed
from onitu.utils import b

token = None
notestore_onitu = None
files_to_ignore = set()
plug = Plug()


# ############################## EVERNOTE ####################################

def register_note_resource(noteMetadata, resource):
    """Register a resource GUID and filename in the metadata of its note."""
    rscFilename = resource.attributes.fileName
    plug.logger.debug(u"Registering resource {} in note {} metadata",
                      rscFilename, noteMetadata.path)
    if noteMetadata.extra.get('resources', None) is None:
        noteMetadata.extra['resources'] = {}
    noteMetadata.extra['resources'][resource.guid] = rscFilename


def update_resource_metadata(onituMetadata, resource, updateFile=False):
    """Updates the Onitu metadata of a resource file. Quite not the same thing
    as updating a note."""
    # Data may not be set so be careful
    if resource.data is not None:
        onituMetadata.size = resource.data.size
    onituMetadata.extra['guid'] = resource.guid
    # noteGuid helps us to remember if a file is a file's resource or not
    onituMetadata.extra['note_guid'] = resource.noteGuid
    onituMetadata.extra['USN'] = resource.updateSequenceNum
    if updateFile:
        plug.update_file(onituMetadata)


def update_note_metadata(onituMetadata, note, updateFile=False):
    """Updates the Onitu metadata of an Evernote note. If updateFile is True,
    call plug.update_file. If not, just call metadata.write"""
    onituMetadata.size = note.contentLength
    onituMetadata.extra['guid'] = note.guid
    onituMetadata.extra['hash'] = note.contentHash
    onituMetadata.extra['USN'] = note.updateSequenceNum
    # Usually this function gets called if an update has been detected, but
    # we must call plug.update_file only if it's a content-related change.
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
            u"Cannot connect to Evernote: {}".format(e)
        )
    plug.logger.debug("Connection successful")


def create_notebook(name):
    plug.logger.debug(u"Creating notebook {}", name)
    try:
        notebook = notestore_onitu.createNotebook(token,
                                                  Types.Notebook(name=name))
    except EDAMUserException as eue:
        raise ServiceError(u"Cannot create notebook - {}".format(eue))
    return notebook


def find_notebook_by_guid(guid, name=None, create=False):
    """Find the notebook with this GUID. If create is True, we create it
    if it doesn't exist"""
    plug.logger.debug(u"Getting notebook with GUID {}", guid)
    try:
        notebook = notestore_onitu.getNotebook(token, guid)
    except EDAMNotFoundException as enfe:
        if create:
            return create_notebook(name)
        else:
            raise ServiceError(u"Notebook with GUID {} not found - {}"
                               .format(guid, enfe))
    except EDAMUserException as eue:
        raise ServiceError(u"Cannot find notebook with GUID {} - {}"
                           .format(guid, eue))
    return notebook


def find_notebook_by_name(name, create=False):
    """Find the notebook named. If create is True, we create the notebook
    if it doesn't exist yet"""
    plug.logger.debug(u"Searching notebook {}", name)
    try:
        for notebook in notestore_onitu.listNotebooks():
            if notebook.name == name:
                plug.logger.debug(u"Found {} notebook", name)
                return notebook
    except (EDAMUserException, EDAMSystemException) as exc:
        raise ServiceError(u"Cannot list notebooks - {}".format(exc))
    if create:
        return create_notebook(name)


def enclose_content_with_markup(content):
    """Enclose some given content with the Evernote boilerplate markup.
    It is useful when creating new notes without this markup, since Evernote
    raises errors in those cases."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
    <en-note>{}</en-note>""".format(content)
    return content


def update_note_content(metadata, content, note=None):
    """Updates the content of an Evernote note with the given content.
    Also provides content hash and length. An existing note can be passed, so
    that it won't be retrieved twice."""
    if note is None:
        # Ask only for note and its content, no resource info
        note = notestore_onitu.getNote(token, metadata.extra['guid'],
                                       True, False, False, False)
    note.content = content
    md5_hash = hashlib.md5()
    md5_hash.update(content)
    md5_hash = md5_hash.digest()
    note.contentHash = md5_hash
    note.contentLength = len(content)
    return note


def create_note(metadata, content, notebook):
    """Creates an Evernote note out of a new file, prior to uploading it."""
    note = Types.Note()
    note.title = metadata.filename
    note = update_note_content(metadata, content, note)
    note.notebookGuid = notebook.guid
    return notestore_onitu.createNote(note)


# ############################# ONITU HANDLERS ###############################

# Unexpected error calling 'move_file': 'str' object has no attribute 'write'
# with updateresource we cannot update the content, only metadata
# @plug.handler()
# def move_file(old_metadata, new_metadata):
#     global notestore_onitu
#     global dev_token
#
#     note = notestore_onitu.getNote(token, old_metadata.extra['guid'],
#                                    False, False, True, False)
#
#     res = note.resources[0]  # Types.Resource()
#     attr = Types.ResourceAttributes()
#     attr.fileName = new_metadata.filename
#     print
#     print "MOVE: New filename =" + attr.fileName
#     print
#
# #    res.guid = note.resources[0].guid
#     res.attributes = attr
#     res.mime = new_metadata.mimetype
#     # notestore_onitu.updateResource(dev_token, res)
#


@plug.handler()
def get_file(metadata):
    # We MUST have a guid when working with Evernote files
    guid = metadata.extra.get('guid', None)
    if guid is None:
        raise DriverError(u"No GUID for file '{}'!".format(metadata.path))
    # We must use a different API call if the file is actually a resource !
    noteGuid = metadata.extra.get('note_guid', None)
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
                           .format(metadata.path, exc))
    return data


# @plug.handler()
# def upload_file(metadata, content):
#     # A couple of helper nested functions to easily handle retries
#     def upload_note(metadata, content):
#         if metadata.extra.get('evernote_guid', None) is None:
#             # Create the note via the Evernote API in case of new file
#             plug.logger.debug(u"Creating note {}".format(metadata.filename))
#             note = create_note(metadata, content)
#         else:
#             # If it is a file already registered to Evernote, just update it
#             plug.logger.debug(u"Updating note {}".format(metadata.filename))
#             note = update_note_content(metadata, content)
#             note = notestore_onitu.updateNote(token, note)
#         return note
#
#     def upload_resource(metadata, content):
#         """The process of updating a resource is quite the same than to delete
#         one."""
#         guid = metadata.extra['evernote_guid']  # guid of the resource
#         plug.logger.debug(u"Updating note resource {} (GUID {})"
#                           .format(metadata.filename, guid))
#         # Get the note and manually update the resource in the resource list
#         # Yep, that's dirty, because there's no dedicated API
#         # call, but it is the official best practice...
#         # note = notestore_onitu.getNote(token, resourceNoteGuid,
#         #                               False, False, False, False)
#         resource = None
#         # Reconstruct the list omitting the concerned resource.
#         for rsc in note.resources:
#             if rsc.guid == guid:
#                 rsc.data = content
#                 resource = rsc
#                 break
#         if resource is None:
#             raise DriverError(u"No Evernote Resource GUID for file {} !"
#                               .format(metadata.filename))
#         plug.logger.debug("Successfully updated the resource")
#         return resource
#
#     # TODO Correctly manage upload_file
#     # If upload_file modifies the content of the note, we have to call
#     # update_file in the end to notify the other drivers
#     update = False
#     try:
#         # If it's a resource
#         if metadata.extra.get('evernote_note_guid', None) is not None:
#             resource = upload_resource(metadata, content)
#         else:
#             note = upload_note(metadata, content)
#     except EDAMUserException as eue:
#         # Evernote can raise content-related errors when the user updates the
#         # note's contents. E.g. when creating a new note, the user may
#         # forget to enclose the content evernote boilerplate markup. It's
#         # likely to raise an error in case of empty note or premature content
#         # start. We must detect those cases and try to add the markup
#         knownErrors = ['Content is not allowed in prolog.',
#                        'Premature end of file.']
#         if (eue.errorCode == EDAMErrorCode.ENML_VALIDATION
#            and eue.parameter in knownErrors):
#             plug.logger.warning("Catched content exception, trying to"
#                                 " fix by putting content in Evernote markup")
#             content = enclose_content_with_markup(content)
#             note = upload_note(metadata, content)  # Try again
#             update = True
#         else:  # A UserException we don't know
#             raise ServiceError(u"Couldn't upload note {}: {}"
#                                .format(metadata.filename, eue))
#     except (EDAMSystemException, EDAMNotFoundException) as exc:
#         raise ServiceError(u"Couldn't upload note {}: {}"
#                            .format(metadata.filename, exc))
#     except Exception as e:
#         raise DriverError("Unexpected error {}".format(e))
#     # If the evernote part was OK, update onitu metadata
#     if metadata.extra.get('evernote_note_guid', None) is not None:
#         update_resource_metadata(metadata, resource)
#     else:
#         # Call plug.update_file if we modified the content by
#         # enclosing ENML markup
#         update_note_metadata(metadata, note, updateFile=update)
#     plug.logger.debug(u"Upload of file {} completed", metadata.filename)
#
#
@plug.handler()
def delete_file(metadata):
    """Handler to delete a file. This gets called for the notes AND for the
    resources. So if the file is an Evernote note, we also delete all the
    files that are its resources on Evernote."""
    plug.logger.debug(u"Deleting {}", metadata.path)
#     resourceNoteGuid = metadata.extra.get('evernote_note_guid', None)
#     try:
#         # We didn't store any owning note GUID for this file
#         # so it must be a note
#         if not resourceNoteGuid:
#             plug.logger.debug(u"Removing note {} (GUID {})",
#                               metadata.filename, resourceNoteGuid)
#             # res = notestore_onitu.deleteNote(token,
#             #                                 metadata.extra['evernote_guid'])
#         else:  # it is a resource of a file
#             guid = metadata.extra['evernote_guid']  # guid of the resource
#             plug.logger.debug(u"Removing note resource {} (GUID {})"
#                               .format(metadata.filename, guid))
#             # Get the note, manually remove the resource in the resource list
#             # Yep, that's dirty, because e.g. the note's markup keeps
#             # referencing a broken resource, but there's no dedicated API
#             # call, it is the official best practice...
#             note = notestore_onitu.getNote(token, resourceNoteGuid,
#                                            False, False, False, False)
#             # Reconstruct the list omitting the concerned resource.
#             note.resources = [rc for rc in note.resources if rc.guid != guid]
#             note = notestore_onitu.updateNote(token, note)
#     except (EDAMUserException, EDAMSystemException,
#             EDAMNotFoundException) as exc:
#         raise ServiceError(u"Unable to delete file {}: {}"
#                            .format(metadata.filename, exc))


# ############################## WATCHER #####################################

class CheckChanges(threading.Thread):
    """A class polling for changes on the Evernote notebook
    Evernote lets us know if we're up-to-date with a sync state number. If
    see our number doesn't match anymore the server's one, we start an
    update."""

    def __init__(self, folder, timer):
        threading.Thread.__init__(self)
        self.stopEvent = threading.Event()
        self.timer = timer
        self.folder = folder
        self.note_store = notestore_onitu
        notebook_db_key = 'nb_{}_guid'.format(folder.path)
        guid = plug.service_db.get(notebook_db_key, default="")
        if guid == "":
            self.notebook = find_notebook_by_name(folder.path, create=True)
        else:
            self.notebook = find_notebook_by_guid(guid, create=True)
        # The last update count of the notebook we're aware of.
        notebook_db_key = 'nb_{}_syncState'.format(folder.path)
        self.nb_syncState = plug.service_db.get(notebook_db_key, default=0)
        # We don't want to paginate. Ask all teh notes in one time
        self.maxNotes = EDAM_USER_NOTES_MAX
        # Filter to include only notes from our notebook
        self.noteFilter = NoteFilter(order=NoteSortOrder.RELEVANCE,
                                     notebookGuid=self.notebook.guid)
        # Note spec to filter even more the findNotesMetadata result
        self.resultSpec = (
            NotesMetadataResultSpec(includeTitle=True,
                                    includeContentLength=True,
                                    includeUpdateSequenceNum=True)
        )
        self.filesToDelete = []

    def update_note_resources(self, note, noteOnituMetadata):
        """Checks if a note's resources are up to date. Returns whether we
        should call metadata.write on the note's metadata or not (depending
        on if we found new resources or not)."""
        if note.resources is None:
            plug.logger.debug("No resource")
            return False
        doWrite = False
        for resource in note.resources:
            # resourceName = resource.attributes.fileName
            plug.logger.debug(u"Processing note {}'s resource {}", note.title,
                              resource.attributes.fileName)
            resourceMetadata = plug.get_metadata(resource.attributes.fileName,
                                                 self.folder)
            onitu_USN = resourceMetadata.extra.get('USN', 0)
            if onitu_USN < resource.updateSequenceNum:
                if onitu_USN == 0:  # new resource
                    register_note_resource(noteOnituMetadata, resource)
                    doWrite = True
                update_resource_metadata(resourceMetadata, resource,
                                         updateFile=True)
            if resourceMetadata.filename in self.filesToDelete:
                del self.filesToDelete[resourceMetadata.filename]
        return doWrite

    def update_note(self, noteMetadata, onituMetadata):
        """Updates a note. Checks that the content has changed by doing
        a hash comparison. Also updates the note's resources."""
        plug.logger.debug(u"Updating file {}", onituMetadata.path)
        # Check the hash first (get the resource data as well)
        note = notestore_onitu.getNote(noteMetadata.guid,
                                       False, False, False, False)
        onituHash = onituMetadata.extra.get('hash', "")
        updateMetadata = False
        updateFile = False
        # The content hash changed: notify an update
        if note.contentHash != onituHash:
            updateFile = True
            plug.logger.debug(u"Note {} updated".format(note.title))
        if not updateFile:
            plug.logger.debug(u"Non content-related update on note {}, "
                              u"updating metadata but won't call "
                              u"plug.update_file", note.title)
        # Now check the resources of the note
        updateMetadata = self.update_note_resources(note, onituMetadata)
        # We could want to call plug.update_file or just metadata.write
        if updateMetadata or updateFile:
            update_note_metadata(onituMetadata, note, updateFile)

    def check_updated(self):
        """Checks for updated notes on the Onitu notebook.
        Loops the findNotesMetadata operation until everything is gone."""
        remaining = 1
        offset = 0
        while remaining:
            res = notestore_onitu.findNotesMetadata(self.noteFilter, offset,
                                                    self.maxNotes,
                                                    self.resultSpec)
            plug.logger.debug("Processing {} notes", res.totalNotes)
            for noteMetadata in res.notes:
                filename = noteMetadata.title + ".enml"
                onituMetadata = plug.get_metadata(filename, self.folder)
                # The flaw in checking the USN is that it increases even for
                # non content-related changes (e.g. a tag added). But that's
                # the best way to do it.
                evernote_usn = noteMetadata.updateSequenceNum
                onitu_usn = onituMetadata.extra.get('USN', 0)
                if onitu_usn < evernote_usn:
                    self.update_note(noteMetadata, onituMetadata)
                else:
                    plug.logger.debug(u"Note {} is up-to-date",
                                      noteMetadata.title)
                # Cross this file out from the deleted files list
                if filename in self.filesToDelete:
                    del self.filesToDelete[filename]
            # Update the offset to ask the rest of the notes next time
            offset = res.startIndex + len(res.notes)
            remaining = res.totalNotes - offset

    def check_deleted(self):
        plug.logger.debug(u"Have {} files to delete in notebook {}",
                          len(self.filesToDelete), self.folder.path)
        for filename in self.filesToDelete:
            # Ignored because this file is currently in a transfer
            if filename in files_to_ignore:
                continue
            metadata = plug.get_metadata(filename, self.folder)
            plug.delete_file(metadata)

    def check_changes(self):
        """The function that will check the notes in the notebook are uptodate
        Evernote doesn't let us check regular and deleted files at the same
        time, so we have to do two separate passes."""
        self.filesToDelete = plug.list(self.folder)
        self.check_updated()
        self.check_deleted()

    def run(self):
        while not self.stopEvent.isSet():
            try:
                # The USN is now an unreliable way of checking updates on a
                # notebook, because it doesn't increment with its notes ones
                # anymore. So the new best practice is to get the global sync
                # state of the account, and check when it has changed. Sadly.
                syncState = notestore_onitu.getSyncState()
                # There has been a new transaction on the notebook
                if self.nb_syncState < syncState.updateCount:
                    plug.logger.debug(u"Server SyncState has changed,"
                                      u" checking notebook {}",
                                      self.folder.path)
                    self.check_changes()
                    # Update ourselves
                    self.nb_syncState = syncState.updateCount
                    plug.service_db.put('nb_{}_syncState'.format(
                                        self.folder.path),
                                        syncState.updateCount)
                else:
                    plug.logger.debug(u"notebook {} is up to date with "
                                      u"sync state {}", self.folder.path,
                                      self.nb_syncState)
            except (EDAMUserException, EDAMSystemException,
                    EDAMNotFoundException) as exc:
                raise ServiceError(u"Error while polling Evernote changes: {}"
                                   .format(exc))
            except ResponseNotReady:
                plug.logger.warning("Cannot poll changes, the notebook data"
                                    " isn't ready.")
            except EscalatorClosed:
                # We are closing
                return
            plug.logger.debug(u"Next check on {} in {} seconds",
                              self.folder.path, self.timer)
            self.stopEvent.wait(self.timer)

    def stop(self):
        self.stopEvent.set()


def start():
    if plug.options['changes_timer'] < 0:
        raise DriverError("Changes timer must be a positive value")

    # Start the Evernote connection and retrieve our note store
    connect_client()
    for folder in plug.folders_to_watch:
        # Launch the changes detection
        check = CheckChanges(folder, plug.options['changes_timer'])
        check.daemon = True
        check.start()

    plug.listen()
