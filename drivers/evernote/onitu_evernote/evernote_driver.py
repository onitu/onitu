import threading
import hashlib
from httplib import ResponseNotReady
from ssl import SSLError

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

def register_note_resource(noteMetadata, resourceData, resourceMetadata):
    """Register a resource GUID and filename in the metadata of its note."""
    rscFilename = resourceMetadata.filename
    plug.logger.debug(u"Registering resource {} in note {} metadata",
                      rscFilename, noteMetadata.path)
    if noteMetadata.extra.get(u'resources', None) is None:
        noteMetadata.extra[u'resources'] = {}
    noteMetadata.extra[u'resources'][resourceData.guid] = rscFilename


def delete_resource(rscMetadata):
    plug.logger.debug(u"Deleting resource {}", rscMetadata.path)
    try:
        noteGuid = rscMetadata.extra[u'note_guid']
        rcGuid = rscMetadata.extra[u'guid']
        note = notestore_onitu.getNote(token, noteGuid,
                                       False, False, False, False)
        note.resources = [rsc for rsc in note.resources if rsc.guid != rcGuid]
        # TODO Parse the note's content and remove the references to this resource
        note = notestore_onitu.updateNote(token, note)
        noteMetadata = plug.get_metadata(u"{}/{}"
                                         .format(rscMetadata.folder.path,
                                                 note.title + u".enml"))
        update_note_metadata(noteMetadata, note, updateSize=False)
    except KeyError as ke:
        raise DriverError(u"Resource {} lacks of extra data ! - {}"
                          .format(rscMetadata.path, ke))
    except (EDAMUserException, EDAMSystemException,
            EDAMNotFoundException) as exc:
        raise ServiceError(u"Unable to delete resource {}: {}"
                           .format(rscMetadata.path, exc))


def delete_note_resources(noteMetadata):
    """Deletes all the resource files bound to the given note metadata."""
    resources = noteMetadata.extra.get(u'resources', {})
    for filename in resources.values():
        rscMetadata = plug.get_metadata("{}/{}"
                                        .format(noteMetadata.folder.path,
                                                filename))
        plug.delete_file(rscMetadata)


def update_resource_metadata(onituMetadata, resource, updateFile=False):
    """Updates the Onitu metadata of a resource file. Quite not the same thing
    as updating a note."""
    # Data may not be set so be careful
    if resource.data is not None:
        onituMetadata.size = resource.data.size
    onituMetadata.extra[u'guid'] = resource.guid
    onituMetadata.extra[u'hash'] = resource.data.bodyHash
    # noteGuid helps us to remember if a file is a file's resource or not
    onituMetadata.extra[u'note_guid'] = resource.noteGuid
    onituMetadata.extra[u'USN'] = resource.updateSequenceNum
    if updateFile:
        plug.update_file(onituMetadata)


def update_note_metadata(onituMetadata, note,
                         updateSize=True, updateFile=False):
    """Updates the Onitu metadata of an Evernote note. If updateFile is True,
    call plug.update_file. If not, just call metadata.write"""
    plug.logger.debug(u"Updating metadata of {}", onituMetadata.path)
    if updateSize:
        onituMetadata.size = note.contentLength
    onituMetadata.extra[u'guid'] = note.guid
    onituMetadata.extra[u'hash'] = note.contentHash
    onituMetadata.extra[u'USN'] = note.updateSequenceNum
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


def find_note_by_title(noteTitle, notebookGuid):
    """Search a note in a notebook with its title."""
    try:
        # Filter to include only notes from our notebook
        noteFilter = NoteFilter(order=NoteSortOrder.RELEVANCE,
                                notebookGuid=notebookGuid)
        # Note spec to filter even more the findNotesMetadata result
        resultSpec = (
            NotesMetadataResultSpec(includeTitle=True,
                                    includeContentLength=True,
                                    includeUpdateSequenceNum=True)
        )
        res = notestore_onitu.findNotesMetadata(noteFilter, 0,
                                                EDAM_USER_NOTES_MAX,
                                                resultSpec)
        for noteMetadata in res.notes:
            if noteMetadata.title == noteTitle:
                plug.logger.debug(u"Found note {}", noteTitle)
                note = notestore_onitu.getNote(token, noteMetadata.guid,
                                               True, False, False, False)  # TODO Include content here ? Do not include resource data ? Decide !
                return note
    except (EDAMUserException, EDAMSystemException,
            EDAMNotFoundException) as exc:
        raise ServiceError(u"Unable to find note {} by its name - {}"
                           .format(noteTitle, exc))
    plug.logger.debug(u"Note {} doesn't exist in notebook guid {}",
                      noteTitle, notebookGuid)
    return None


def enclose_content_with_markup(content):
    """Enclose some given content with the Evernote boilerplate markup.
    It is useful when creating new notes without this markup, since Evernote
    raises errors in those cases."""
    content = """<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd">
    <en-note>{}</en-note>""".format(content)
    return content


def update_note_content(metadata, content, note=None, updateNote=True):
    """Updates the content of an Evernote note with the given content.
    Also provides content hash and length. An existing note can be passed, so
    that it won't be retrieved twice."""
    try:
        if note is None:
            # Ask only for note and its content, no resource
            note = notestore_onitu.getNote(token, metadata.extra[u'guid'],
                                           True, False, False, False)
        note.content = content
        md5_hash = hashlib.md5()
        md5_hash.update(content)
        md5_hash = md5_hash.digest()
        # Sometimes we have problems with local storages sending several
        # updates notifications even though the contents of the file haven't
        # changed... So this is to prevent useless note updates !
        if md5_hash == note.contentHash:
            return None
        note.contentHash = md5_hash
        note.contentLength = len(content)
        if updateNote:
            note = notestore_onitu.updateNote(token, note)
    except (EDAMUserException, EDAMSystemException,
            EDAMNotFoundException) as exc:
        raise ServiceError(u"Unable to update note {} - {}"
                           .format(metadata.path, exc))
    return note


def create_note(metadata, content, notebook, title=None):
    """Creates an Evernote note out of a new file, prior to uploading it."""
    new_metadata = None  # in case of a move_file
    # TODO Metadata.mimetype isn't reliable yet...
    # mime = metadata.mimetype
    # plug.logger.debug(mime)
    # if not mime.startswith(u"text") and not mime.endswith(u"xml"):
    #    raise DriverError(u"Trying to create note {}, but it isn't text!"
    #                      .format(metadata.path))

    if title is None:
        title = metadata.filename
    else:
        # Do some checks on metadata.filename to send the note with correct
        # filename. Otherwise it will just ruin the logic based on the
        # assumption we upload note "title.enml" in a subfolder named "title".
        # If we're here we already know we're in the folder. So we can strip
        expected = u"{0}/{0}.enml".format(title)
        if metadata.filename != expected:
            new_metadata = plug.move_file(metadata, expected)

    try:
        note = Types.Note()
        note.title = title
        # Update note's contents without calling updateNote
        note = update_note_content(metadata, content, note=note,
                                   updateNote=False)
        note.notebookGuid = notebook.guid
        note = notestore_onitu.createNote(note)
    except (EDAMUserException, EDAMSystemException,  # TODO manage markup enclosing problems
            EDAMNotFoundException) as exc:
        raise ServiceError(u"Unable to create note {} - {}"
                           .format(metadata.path, exc))

    metadata_to_update = metadata
    if new_metadata is not None:
        metadata_to_update = new_metadata
    update_note_metadata(metadata_to_update, note)
    return note


# ############################# ONITU HANDLERS ###############################

@plug.handler()
def get_file(metadata):
    # We MUST have a guid when working with Evernote files
    guid = metadata.extra.get(u'guid', None)
    if guid is None:
        raise DriverError(u"No GUID for file '{}'!".format(metadata.path))
    # We must use a different API call if the file is actually a resource !
    noteGuid = metadata.extra.get(u'note_guid', None)
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


@plug.handler()
def upload_file(metadata, content):
    if metadata.filename in files_to_ignore:
        return
    files_to_ignore.add(metadata.filename)
    firstSlashIdx = metadata.filename.find(u"/")
    noteTitle = metadata.filename[:firstSlashIdx]
    # The file isn't in a directory called "title"
    if firstSlashIdx == -1:
        pass  # TODO Move the file in the directory
    else:
        guid = metadata.extra.get('guid', None)
        # No GUID: new file
        if guid is None:
            notebook = find_notebook_by_name(metadata.folder.path,
                                             create=True)
            note = find_note_by_title(noteTitle, notebook.guid)
            # The note exists: add this as a resource
            if note is not None:
                pass  # TODO
            # The note doesn't exist: try to create the note with this file
            else:
                create_note(metadata, content, notebook, title=noteTitle)
        # This is a file already known by Evernote, note or resource
        else:
            rscNoteGuid = metadata.extra.get('note_guid', None)
            # it's the note
            if rscNoteGuid is None:
                plug.logger.debug("Note new content: {}", content)
                note = update_note_content(metadata, content, note=None)
                if note is None:
                    plug.logger.debug(u"Uploaded content for {} is the same "
                                      u"than on Evernote, no update done",
                                      metadata.path)
                else:
                    update_note_metadata(metadata, note, updateSize=False)
            # it's an updated resource
            else:
                # TODO Get the note, add a resource, and parse the contents to add a reference to the new resource
                pass  # update_resource(metadata, content)
    files_to_ignore.remove(metadata.filename)


@plug.handler()
def abort_upload(metadata):
    if metadata.filename in files_to_ignore:
        files_to_ignore.remove(metadata.filename)


@plug.handler()
def delete_file(metadata):
    """Handler to delete a file. This gets called for the notes AND for the
    resources. So if the file is an Evernote note, we also delete all the
    files that are its resources on Evernote."""
    plug.logger.debug(u"Deleting {}", metadata.path)
    resourceNoteGUID = metadata.extra.get(u'note_guid', None)
    try:
        if resourceNoteGUID is None:
            delete_note_resources(metadata)
            notestore_onitu.deleteNote(token, metadata.extra['guid'])
            plug.delete_file(metadata)
        else:
            plug.logger.debug(u"DELETE RESOURCE {}", metadata.path)  # TODO TMP
            delete_resource(metadata)
    except (EDAMUserException, EDAMSystemException,
            EDAMNotFoundException) as exc:
        raise ServiceError(u"Unable to delete file {}: {}"
                           .format(metadata.filename, exc))


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
        notebook_db_key = u'nb_{}_guid'.format(folder.path)
        guid = plug.service_db.get(notebook_db_key, default="")
        if guid == "":
            self.notebook = find_notebook_by_name(folder.path, create=True)
        else:
            self.notebook = find_notebook_by_guid(guid, create=True)
        # The last update count of the notebook we're aware of.
        notebook_db_key = u'nb_{}_syncState'.format(folder.path)
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
            plug.logger.debug(u"No resource for {}", note.title)
            return False
        doWrite = False
        for resource in note.resources:
            # resourceName = resource.attributes.fileName
            plug.logger.debug(u"Processing note {}'s resource {}", note.title,
                              resource.attributes.fileName)
            rscPath = u"{}/{}".format(note.title,
                                      resource.attributes.fileName)
            resourceMetadata = plug.get_metadata(rscPath,
                                                 self.folder)
            onitu_USN = resourceMetadata.extra.get(u'USN', 0)
            if onitu_USN < resource.updateSequenceNum:
                if onitu_USN == 0:  # new resource
                    register_note_resource(noteOnituMetadata, resource,
                                           resourceMetadata)
                    doWrite = True
                bodyHash = resourceMetadata.extra.get(u'hash', "")
                updateFile = True
                if bodyHash == resource.data.bodyHash:
                    plug.logger.debug(u"USN of {} changed but content is "
                                      u"unchanged, so updating metadata USN "
                                      u"only", resourceMetadata.path)
                    updateFile = False
                update_resource_metadata(resourceMetadata, resource,
                                         updateFile=updateFile)
            if resourceMetadata.filename in self.filesToDelete:
                del self.filesToDelete[resourceMetadata.filename]
        return doWrite

    def update_note(self, noteMetadata, onituMetadata):
        """Updates a note. Checks that the content has changed by doing
        a hash comparison. Also updates the note's resources."""
        note = notestore_onitu.getNote(noteMetadata.guid,
                                       False, False, False, False)
        updateMetadata = False
        updateFile = False
        # The flaw in checking the USN is that it increases even for
        # non content-related changes (e.g. a tag added). But that's
        # the best way to do it.
        evernote_usn = noteMetadata.updateSequenceNum
        onitu_usn = onituMetadata.extra.get(u'USN', 0)
        if onitu_usn < evernote_usn:
            plug.logger.debug(u"Updating file {}", onituMetadata.path)
            # Check the content hash first
            onituHash = onituMetadata.extra.get(u'hash', "")
            if not note.active:
                plug.logger.debug(u"{} is in the trashbin "
                                  u"(probably from Onitu)", note.title)
                return
            # The content hash changed: notify an update
            if note.contentHash != onituHash:
                updateFile = True
                plug.logger.debug(u"Note {} updated".format(note.title))
            if not updateFile:
                plug.logger.debug(u"Non content-related update on note {}, "
                                  u"updating metadata but won't call "
                                  u"plug.update_file", note.title)
        else:
            plug.logger.debug(u"Note {} is up-to-date",
                              noteMetadata.title)
        # Check the resources of the note in every case, because otherwise if
        # the note is up-to-date, resources aren't getting processed and are
        # deleted on Onitu side !
        updateMetadata = self.update_note_resources(note, onituMetadata)
        # We could want to call plug.update_file or just metadata.write
        if updateMetadata or updateFile:
            update_note_metadata(onituMetadata, note, updateFile=updateFile)

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
                filename = u"{0}/{0}.enml".format(noteMetadata.title)
                onituMetadata = plug.get_metadata(filename, self.folder)
                self.update_note(noteMetadata, onituMetadata)
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
                    plug.service_db.put(u'nb_{}_syncState'.format(
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
            except (SSLError, AttributeError) as err:
                # Sometimes these are warning thrown by the Thrift library
                # used by evernote, for no real reason. Can't do much for it
                plug.logger.warning(u"Unexpected error in check changes of"
                                    u" {}: {}".format(self.folder.path, err))
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
