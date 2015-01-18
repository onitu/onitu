import os
import urllib
import threading
from io import BytesIO
from datetime import datetime

from .flickrapi import FlickrAPI
from .flickrapi.auth import FlickrAccessToken
from .flickrapi.exceptions import FlickrError

from onitu.plug import Plug, ServiceError, DriverError
from onitu.escalator.client import EscalatorClosed
from onitu.utils import u

plug = Plug()
API_KEY = '66a1c393c8de67fbeef54bb785375e06'
API_SECRET = '5bfbc7256872d085'
flickr = None
# Used for tests, when plug.options['png_header'] is True.
PNG_HEADER = '\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'


class FlickrHandler():
    """A class to handle Flickr API calls and provide a set of utilities
    to efficiently use it"""
    def __init__(self, key, secret, oauth_token, oauth_token_secret):
        self.api_key = key
        self.api_secret = secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret
        # Dict to match photosets names->IDs
        self.photosetIDs = plug.service_db.get('photosetIDs', default={})
        self.flickr_api = None
        self.connect_API()
        self.user_id = self.flickr_api.flickr.token_cache.token.user_nsid

    def connect_API(self):
        token = FlickrAccessToken(self.oauth_token, self.oauth_token_secret,
                                  u'delete')
        self.flickr_api = FlickrAPI(self.api_key, self.api_secret,
                                    format=u"etree", token=token)
        if not self.flickr_api.token_valid(perms=u'delete'):
            raise DriverError("Failed to connect to Flickr, please check your"
                              " authentication credentials")
        plug.logger.debug("Connection to Flickr successful")

    def get_photoset_ID(self, searchedPhotoset=None):
        """Store the ID matching a given photoset name. If no photoset name is
        given, stores the ID of all the existing photosets. Returns the given
        photoset ID or, if we aren't searching for a particular one, return the
        entire dict."""
        plug.logger.debug(u"Seaching for {} photoset ID"
                          .format(searchedPhotoset))
        # If already in database
        if self.photosetIDs.get(searchedPhotoset, None) is not None:
            return self.photosetIDs[searchedPhotoset]
        sets = self.flickr_api.photosets.getList()
        storeAll = searchedPhotoset is None
        for photoset in sets.find('photosets').findall('photoset'):
            photosetTitle = photoset.find('title').text
            if photosetTitle == searchedPhotoset or storeAll:
                self.photosetIDs[photosetTitle] = photoset.attrib['id']
                if not storeAll:  # found the One
                    break
        plug.logger.debug(u"Done searching {} photoset ID, updating database"
                          .format(searchedPhotoset))
        # Keep the database up-to-date
        plug.service_db.put('photosetIDs', self.photosetIDs)
        if storeAll:
            return self.photosetIDs
        else:
            searchedID = ''
            try:
                searchedID = self.photosetIDs[searchedPhotoset]
            except KeyError:
                raise DriverError(u"No Flickr ID for album name '{}'!"
                                  .format(searchedPhotoset))
            return searchedID

    def download_photo_content(self, photo_id, size="Original"):
        """Downloads the binary data of a Flickr image. Gets the image in
        original size by default. The possibilities may be:
        Square, Large Square, Thumbnail Small, Small 320, Medium, Medium 640,
        Medium 800, Large, Original."""
        plug.logger.debug(u"Downloading contents from photo ID {}"
                          .format(photo_id))
        rsp = self.flickr_api.photos.getSizes(photo_id=photo_id)
        sizes = rsp.find('sizes').findall('size')
        orig = next((elem for elem in sizes if elem.attrib['label'] == size),
                    None)
        if orig is None:
            raise ServiceError(u"No URL for photo ID '{}' at size '{}' !"
                               .format(photo_id, size))
        url = orig.attrib['source']
        try:
            data = urllib.request.urlopen(url)
        except AttributeError:  # In Python 2
            data = urllib.urlopen(url)
        return data.read()

    def get_photo_IDs_of_photoset(self, photosetID):
        """Retrieves the photo_id of every photo in a photoset."""
        photosIDs = [photo.get('id')
                     for photo in self.flickr_api.walk_set(photosetID)]
        return photosIDs

    def upload_photo_in_photoset(self, filename, data, photosetName):
        # Respecting the Flickr convention that wants that photo titles be
        # without file extension.
        title = os.path.splitext(filename)[0]
        desc = "Uploaded by Onitu"
        plug.logger.debug(u"Uploading photo {} with title {}"
                          .format(filename, title))
        resp = self.flickr_api.upload(filename=filename, fileobj=data,
                                      title=title, description=desc,
                                      format='etree')
        photoID = resp.find('photoid').text
        # Now add the uploaded photo to the photoset of the folder
        try:
            photosetID = flickr.get_photoset_ID(photosetName)
        except DriverError:  # This means the album has been deleted
            # We need to recreate it by setting the given photo as primary.
            plug.logger.debug(u"No {} photoset on Flickr, creating it"
                              .format(photosetName))
            self.create_photoset_with_photo(photosetName, photoID)
            return photoID
        # The album already exists, no error
        plug.logger.debug(u"Adding {} (ID: {}) to photoset {} (ID: {})"
                          .format(filename, photoID,
                                  photosetName, photosetID))
        try:
            flickr.flickr_api.photosets.addPhoto(photoset_id=photosetID,
                                                 photo_id=photoID)
        except FlickrError as fe:
            if fe.message == "Error: 1: Photoset not found":
                plug.logger.debug(u"Photoset {} doesn't exist anymore,"
                                  u"recreating it".format(photosetName))
                # This kind of "memory effect" can occur if e.g. we delete the
                # last photo of an album, since in that case Flickr deletes
                # the album altogether! Since we cache photoset IDs, it
                # happens we keep an invalid photoset ID. Recreating the
                # photoset should fix the problem.
                self.create_photoset_with_photo(photosetName, photoID)
            else:
                raise
        return photoID

    def create_photoset_with_photo(self, photosetName, photoID):
        desc = "Created by Onitu"
        resp = self.flickr_api.photosets.create(title=photosetName,
                                                description=desc,
                                                primary_photo_id=photoID)
        photosetID = resp.find('photoset').attrib['id']
        self.photosetIDs[photosetName] = photosetID
        plug.service_db.put('photosetIDs', self.photosetIDs)
        plug.logger.debug(u"Photoset {} successfully created, ID: {}"
                          .format(photosetName, photosetID))

    def get_photo_ID(self, photoName, photosetID=None):
        """Retrieves the ID of a photo. Only for tests purposes."""
        photos = None
        if photosetID is None:
            resp = self.flickr_api.people.getPhotos(user_id=u"me")
            photos = resp.find('photos').findall('photo')
        else:
            resp = self.flickr_api.photosets.getPhotos(photoset_id=photosetID)
            photos = resp.find('photoset').findall('photo')
        for photo in photos:
            if photo.attrib['title'] == photoName:
                return photo.attrib['id']
        return None

# ############################## ONITU ######################################


@plug.handler()
def get_file(metadata):
    """ Return an image's contents."""
    photo_id = metadata.extra.get('photo_id', None)
    if photo_id is None:
        raise DriverError(u"No photo ID for file '{}'"
                          .format(metadata.filename))
    data = flickr.download_photo_content(photo_id)
    # This is to fix any temporary size set by the check changes thread.
    # Ideally the get_file handler shouldn't have to do that.
    dataLen = len(data)
    if metadata.size != dataLen:
        metadata.size = dataLen
        metadata.write()
    return data


@plug.handler()
def upload_file(metadata, content):
    filename = metadata.filename
    # Used for tests.
    if plug.options['png_header']:
        content = PNG_HEADER + content
    data = BytesIO(content)
    try:
        # If it has no photo ID it means it's a new file going to Flickr.
        if metadata.extra.get('photo_id', None) is None:
            photoID = flickr.upload_photo_in_photoset(filename, data,
                                                      metadata.folder.path)
            # Retrieve the photo ID given to the file by Flickr and save it
            metadata.extra['photo_id'] = photoID
            metadata.write()
        # If the file is known to Flickr we must call replace instead.
        else:
            photoID = metadata.extra['photo_id']
            plug.logger.debug(u"Replacing photo {} (photo ID {})"
                              .format(filename, photoID))
            flickr.flickr_api.replace(filename=filename,
                                      photo_id=photoID,
                                      fileobj=data, format='etree')
    except FlickrError as fe:
        raise ServiceError(u"Failed to upload photo {}: error {} {}"
                           .format(filename, fe.code, fe.message))
    now = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds())
    metadata.extra['last_update'] = now
    metadata.write()
    plug.logger.debug(u"Done uploading photo {}".format(metadata.filename))


@plug.handler()
def delete_file(metadata):
    photoID = metadata.extra.get('photo_id', None)
    if photoID is None:
        raise DriverError(u"No photo ID for file {}!"
                          .format(metadata.filename))
    try:
        flickr.flickr_api.photos.delete(photo_id=photoID)
    except FlickrError as fe:
        raise ServiceError(u"Failed to delete photo {}: error {} {}"
                           .format(metadata.filename, fe.code, fe.message))
    plug.logger.debug(u"Deleted photo {} (ID {})"
                      .format(metadata.filename, photoID))


@plug.handler()
def move_file(old_metadata, new_metadata):
    plug.logger.debug(u"Moving photo {} to {}"
                      .format(old_metadata.filename, new_metadata.filename))
    photoID = old_metadata.extra['photo_id']
    if photoID is None:
        raise DriverError(u"No Photo ID for {} !"
                          .format(old_metadata.filename))
    # Respecting the Flickr convention that wants that photo titles be
    # without file extension.
    title = os.path.splitext(new_metadata.filename)[0]
    try:
        flickr.flickr_api.photos.setMeta(photo_id=photoID, title=title)
    except FlickrError as fe:
        raise ServiceError(u"Failed to move file {} to {} on Flickr: {}"
                           .format(old_metadata.filename,
                                   new_metadata.filename, fe.message))
    new_metadata.extra['photo_id'] = photoID
    now = int((datetime.utcnow() - datetime(1970, 1, 1)).total_seconds())
    new_metadata.extra['last_update'] = now
    new_metadata.write()
    plug.logger.debug(u"Successfully moved {} to {}"
                      .format(old_metadata.filename, new_metadata.filename))


class CheckChanges(threading.Thread):
    """A class spawned in a thread to poll for changes on the Dropbox account.
    Dropbox works with deltas so we have to periodically send a request to
    Dropbox with our current delta to know what has changed since we retrieved
    it."""

    def __init__(self, folder, timer):
        threading.Thread.__init__(self)
        self.stopEvent = threading.Event()
        self.folder = folder
        self.timer = timer
        self.photosetID = flickr.get_photoset_ID(self.folder.path)
        # Set default as 1 for the last update timestamp because Flickr throws
        # an error if we start from 0... -.-
        self.lastUpdateTimestamp = plug.service_db.get('timestamp', default=1)
        plug.logger.debug("Getting timestamp {} out of database"
                          .format(self.lastUpdateTimestamp))

    def run(self):
        while not self.stopEvent.isSet():
            try:
                # Getting it every time because of the photoset ID
                # modifications that could occur during runtime (album
                # automatic deletions, etc.)
                self.photosetID = flickr.get_photoset_ID(self.folder.path)
                self.check_photoset()
            except FlickrError as fe:
                warn = u"An unknown Flickr error occurred: {}".format(
                       fe.message)
                if fe.message == u"Error: 1: Photoset not found":
                    warn = (u"The album {} doesn't exist on Flickr."
                            .format(self.folder.path))
                plug.logger.warning(warn)
            except EscalatorClosed:
                # We are closing
                return
            plug.logger.debug(u"Waiting {} seconds before checking album '{}'"
                              u" again".format(self.timer, self.folder.path))
            self.stopEvent.wait(self.timer)

    def stop(self):
        self.stopEvent.set()

    def check_photoset(self):
        # First retrieve the photos updated since last time.
        # Flickr doesn't provide a way to do it for just a particular album
        ts = self.lastUpdateTimestamp
        extra = 'last_update,original_format'
        rsp = flickr.flickr_api.photos.recentlyUpdated(min_date=ts,
                                                       extras=extra)
        photos = rsp.find('photos')
        nbNewPhotos = photos.attrib['total']
        if nbNewPhotos == '0':  # No change
            plug.logger.debug("No new photos right now")
            return
        plug.logger.debug("Got {} new photos".format(nbNewPhotos))
        # Get all the IDs of the photos contained in the watched album
        # We need to do it to keep up-to-date
        photosetIDs = flickr.get_photo_IDs_of_photoset(self.photosetID)
        for photo in photos.findall('photo'):
            plug.logger.debug(u"Checking {}".format(photo.attrib['title']))
            # If this photo is in our album
            if photo.attrib['id'] in photosetIDs:
                # check if we should update it
                self.process_photo(photo)
            else:
                plug.logger.debug(u"Photo {} isn't in album {}"
                                  .format(photo.attrib['title'],
                                          self.folder.path))
        # Update the timestamp to ask changes since now, next time
        self.update_timestamp()

    def process_photo(self, photo):
        # Add the extension since Flickr strips it
        filename = u"{}.{}".format(photo.attrib['title'],
                                   photo.attrib['originalformat'])
        plug.logger.debug(u"Getting metadata of {}".format(filename))
        metadata = plug.get_metadata(filename, folder=self.folder)
        onituLastUpdate = metadata.extra.get('last_update', None)
        flickrLastUpdate = int(photo.attrib['lastupdate'])
        # if new file or the update time is greater than the one
        # recorded by onitu
        if (onituLastUpdate is None
           or onituLastUpdate < flickrLastUpdate):
            # Store the photo ID if it's a new file to Onitu
            if onituLastUpdate is None:
                metadata.extra['photo_id'] = photo.attrib['id']
                # Setting a TEMPORARY size because there's no way to ask
                # Flickr what is the size in bytes of a photo (it sucks !)
                # Setting a size > 0 will trigger the get_file handler.
                # We check and update the metadata size with the binary
                # data length there, if necessary.
                metadata.size = 1
            metadata.extra['last_update'] = flickrLastUpdate
            plug.logger.debug(u"Updating {}".format(filename))
            plug.update_file(metadata)
        else:
            plug.logger.debug(u"Photo {} is up-to-date"
                              .format(filename))

    def update_timestamp(self):
        nowInSecs = (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
        nowInSecs = int(nowInSecs)
        self.lastUpdateTimestamp = nowInSecs
        plug.service_db.put('timestamp', nowInSecs)


def start():
    global flickr
    flickr = FlickrHandler(API_KEY, API_SECRET,
                           u(plug.options['oauth_token']),
                           u(plug.options['oauth_token_secret']))
    for folder in plug.folders_to_watch:
        plug.logger.debug(u"Starting check change thread on album {}"
                          .format(folder.path))
        check = CheckChanges(folder, plug.options['changes_timer'])
        check.daemon = True
        check.start()
    plug.listen()
