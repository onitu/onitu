import urllib
import threading
from datetime import datetime

from flickrapi import FlickrAPI
from flickrapi.auth import FlickrAccessToken

from onitu.plug import Plug, ServiceError, DriverError
from onitu.escalator.client import EscalatorClosed

plug = Plug()
api_key = '66a1c393c8de67fbeef54bb785375e06'
api_secret = '5bfbc7256872d085'
flickr = None


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
        self.connectAPI()
        self.user_id = self.flickr_api.flickr.token_cache.token.user_nsid

    def connectAPI(self):
        token = FlickrAccessToken(self.oauth_token, self.oauth_token_secret,
                                  'delete')
        self.flickr_api = FlickrAPI(self.api_key, self.api_secret,
                                    format="etree", token=token)
        if not self.flickr_api.token_valid(perms='delete'):
            raise DriverError("Failed to connect to Flickr, please check your"
                              "authentication credentials")
        plug.logger.debug("Connection to Flickr successful")

    def getPhotosetID(self, searchedPhotoset=None):
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
            return self.photosetIDs[searchedPhotoset]

    def downloadPhotoContent(self, photo_id, size="Original"):
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
            raise ServiceError("No URL for photo ID '{}' at size '{}' !"
                               .format(photo_id, size))
        url = orig.attrib['source']
        try:
            data = urllib.request.urlopen(url)
        except AttributeError:  # In Python 2
            data = urllib.urlopen(url)
        return data.read()

    def getPhotoIDsOfPhotoset(self, photosetID):
        """Retrieves the photo_id of every photo in a photoset."""
        photosIDs = [photo.get('id')
                     for photo in self.flickr_api.walk_set(photosetID)]
        return photosIDs


# ############################## ONITU ######################################


@plug.handler()
def get_chunk(metadata, offset, size):
    plug.logger.debug("GET CHUNK")


@plug.handler()
def get_file(metadata):
    """ Return an image's contents."""
    plug.logger.debug("DEBUG")
    photo_id = metadata.extra.get('photo_id', None)
    if photo_id is None:
        raise DriverError(u"No photo ID for file '{}'"
                          .format(metadata.filename))
    return flickr.downloadPhotoContent(photo_id)


@plug.handler()
def upload_file(metadata, content):
    print("UPLOAD FILE")


@plug.handler()
def start_upload(metadata):
    print("START UPLOAD")


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    print("UPLOAD CHUNK")


@plug.handler()
def end_upload(metadata):
    print("END UPLOAD")


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
        self.photosetID = flickr.getPhotosetID(self.folder.path)
        # Set default as 1 for the last update timestamp because Flickr throws
        # an error if we start from 0... -.-
        self.lastUpdateTimestamp = plug.service_db.get('timestamp', default=1)
        plug.logger.debug("Getting timestamp {} out of database"
                          .format(self.lastUpdateTimestamp))

    def run(self):
        while not self.stopEvent.isSet():
            try:
                self.checkPhotoset()
            except EscalatorClosed:
                # We are closing
                return
            plug.logger.debug(u"Waiting {} seconds before checking album '{}'"
                              u" again".format(self.timer, self.folder.path))
            self.stopEvent.wait(self.timer)

    def stop(self):
        self.stopEvent.set()

    def checkPhotoset(self):
        # First retrieve the photos updated since last time.
        # Flickr doesn't provide a way to do it for just a particular album
        ts = self.lastUpdateTimestamp
        extra = 'last_update,original_format'
        rsp = flickr.flickr_api.photos.recentlyUpdated(min_date=ts,
                                                       extras=extra)
        photos = rsp.find('photos')
        nbNewPhotos = photos.attrib['total']
        if nbNewPhotos == 0:  # No change
            plug.logger.debug("No new photos right now")
            return
        plug.logger.debug("Got {} new photos".format(nbNewPhotos))
        # Get all the IDs of the photos contained in the watched album
        # We need to do it to keep up-to-date
        photosetIDs = flickr.getPhotoIDsOfPhotoset(self.photosetID)
        for photo in photos.findall('photo'):
            plug.logger.debug("Checking {}".format(photo.attrib['title']))
            # If this photo is in our album
            if photo.attrib['id'] in photosetIDs:
                # check if we should update it
                self.processPhoto(photo)
        # Update the timestamp to ask changes since now, next time
        self.updateTimestamp()

    def processPhoto(self, photo):
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
            metadata.extra['last_update'] = flickrLastUpdate
            plug.logger.debug(u"Updating {}".format(filename))
            plug.update_file(metadata)

    def updateTimestamp(self):
        nowInSecs = (datetime.utcnow() - datetime(1970, 1, 1)).total_seconds()
        nowInSecs = int(nowInSecs)
        self.lastUpdateTimestamp = nowInSecs
        plug.service_db.put('timestamp', nowInSecs)


def start():
    global flickr

    flickr = FlickrHandler(api_key, api_secret,
                           plug.options['oauth_token'],
                           plug.options['oauth_token_secret'])
    for folder in plug.folders_to_watch:
        plug.logger.debug(u"Starting check change thread on album {}"
                          .format(folder.path))
        check = CheckChanges(folder, plug.options['changes_timer'])
        check.daemon = True
        check.start()

    plug.listen()
