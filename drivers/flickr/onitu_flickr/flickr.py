import urllib

import flickrapi

from onitu.plug import Plug, ServiceError, DriverError

plug = Plug()
api_key = '66a1c393c8de67fbeef54bb785375e06'
api_secret = '5bfbc7256872d085'
flickr = None

class Flickr():
    def __init__(self, key, secret):
        self.api_key = key
        self.api_secret = secret
        # Dict to match photosets names->IDs
        self.photosetIDs = plug.service_db.get('photosetIDs', default={})
        self.flickr_api = None
        self.connectAPI()
        self.user_id = self.flickr_api.flickr.token_cache.token.user_nsid

    def connectAPI(self):
        self.flickr_api = flickrapi.FlickrAPI(self.api_key, self.api_secret,
                                              format="parsed-json")

    def getPhotosetID(self, searchedPhotoset=None):
        """Store the ID matching a given photoset name. If no photoset name is
        given, stores the ID of all the existing photosets."""
        plug.logger.debug("Seaching for {} photoset ID"
                          .format(searchedPhotoset))
        # If already in database
        if self.photosetIDs.get(searchedPhotoset, None) is not None:
            return self.photosetIDs[searchedPhotoset]
        sets = self.flickr_api.photosets.getList(user_id=self.user_id)
        storeAll = searchedPhotoset is None
        for photoset in sets.find('photosets').findall('photoset'):
            photosetTitle = photoset.find('title').text
            if photosetTitle == searchedPhotoset or storeAll:
                self.photosetIDs[photosetTitle] = photoset.attrib['id']
                if not storeAll:  # found the One
                    break
        plug.logger.debug("Done searching {} photoset ID, updating database"
                          .format(searchedPhotoset))
        plug.service_db.put('photosetIDs', self.photosetIDs)  # Keep the database up-to-date
        if storeAll:
            return self.photosetIDs
        else:
            return self.photosetIDs[searchedPhotoset]

    def downloadPhotoContent(self, photo_id, size="Original"):
        """Downloads the binary data of a Flickr image. Gets the image in
        original size by default. The possibilities may be:
        Square, Large Square, Thumbnail Small, Small 320, Medium, Medium 640,
        Medium 800, Large, Original."""
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


def connectToFlickr():
    global flickr

    if flickr is not None:
        flickr = Flickr(api_key, api_secret)
    else:
        flickr.connectAPI()


# ############################## ONITU ######################################

@plug.handler()
def get_file(metadata):
    """ Return an image's contents."""
    photo_id = metadata.extra.get('photo_id', None)
    if photo_id is None:
        raise DriverError("No photo ID for file '{}'"
                          .format(metadata.filename))
    return flickr.downloadPhotoContent(photo_id)


@plug.handler()
def upload_file(self, metadata, content):

        photo_id = self.load_photo_id(metadata)
        tag = metadata.extra['tag']
        title = metadata.filename

        params = {
            'format': 'json',
            'nojsoncallback': '1',
            'photo_id': photo_id,  # only used for replacement
            'title': title,
            'description': 'Uploaded by onitu',
            'tags': tag,
            'is_public': '0',
            'is_friend': '0',
            'is_family': '0',
            'safety_level': '1',
            'hidden': '1'
        }

        params = {k: v for k, v in params.items() if v is not None}

        url = self.replace_url if photo_id else self.upload_url
        r = self.do_upload(url, content, params=params).content

        tree = ElementTree(fromstring(r)).getroot()
        photo_id = tree.find('photoid').text
        r = self.list_photosets()

        if self.photoset_id is None:
            photoset_list = r.json()['photosets']['photoset']
            for p in photoset_list:
                if (p['title']['_content'] == root and
                        p['description']['_content'] == 'onitu'):
                    self.photoset_id = p['id']
                    break

        if self.photoset_id is not None:
            self.add_photo_to_photoset(photo_id, self.photoset_id)
        else:
            r = self.create_photoset(root, photo_id, 'onitu')
            self.photoset_id = r.json()['photoset']['id']

        metadata.extra['id'] = photo_id
        metadata.write()



def delete_file(self, metadata):

        photo_id = self.load_photo_id(metadata)
        if photo_id:
            params = {
                'format': 'json',
                'nojsoncallback': '1',
                'method': 'flickr.photos.delete',
                'photo_id': photo_id
            }

            self.call(requests.get, self.rest_url, params=params,
                      auth=self.oauth)

def get_tag_id(self, photo_id, tag_name):
        try:
            tags = self.get_file_info(photo_id)['photo']['tags']['tag']
        except KeyError:
            plug.logger.warning(
                "get_tag_id: Cannot find tag id of tag '{}'".format(tag_name))
            return None
        for tag in tags:
            if tag['raw'] == tag_name:
                return tag['id']
        return None

def move_file(self, old, new):

        photo_id = self.load_photo_id(old)
        new_tag = self.create_tag(new)

        if photo_id:
            self.rename_file(photo_id, new.filename)
            tag_id = self.load_tag_id(old)
            if tag_id:
                self.remove_tag(tag_id)
                self.add_tags(photo_id, new_tag)
                new.extra['tag'] = new_tag
                new.write()

        if not photo_id or not tag_id:
            plug.logger.warning(
                "move_file: Cannot move file '{}'".format(old.filename))

def get_file_info(self, photo_id):
        """ Return a json with photo infos """

        params = {
            'format': 'json',
            'nojsoncallback': '1',
            'method': 'flickr.photos.getInfo',
            'photo_id': photo_id
        }

        r = self.call(requests.get, self.rest_url, params=params,
                      auth=self.oauth)
        return r.json()

def remove_tag(self, tag_id):

        params = {
            'format': 'json',
            'nojsoncallback': '1',
            'method': 'flickr.photos.removeTag',
            'tag_id': tag_id
        }

        self.call(requests.post, self.rest_url, params=params, auth=self.oauth)

def add_tags(self, photo_id, tags):

        params = {
            'format': 'json',
            'nojsoncallback': '1',
            'method': 'flickr.photos.addTags',
            'photo_id': photo_id,
            'tags': tags
        }

        self.call(requests.post, self.rest_url, params=params, auth=self.oauth)

def rename_file(self, photo_id, title):

        params = {
            'format': 'json',
            'nojsoncallback': '1',
            'method': 'flickr.photos.setMeta',
            'photo_id': photo_id,
            'title': title,
            'description': 'Uploaded by onitu'  # required parameter
        }

        self.call(requests.post, self.rest_url, params=params, auth=self.oauth)

# ############################# PHOTOSETS ###################################

def list_photosets(self):
        params = {
            'format': 'json',
            'nojsoncallback': '1',
            'user_id': self.user_id,
            'method': 'flickr.photosets.getList'
        }

        return self.call(requests.get, self.rest_url, params=params,
                         auth=self.oauth)

def add_photo_to_photoset(self, photo_id, photoset_id):
        params = {
            'format': 'json',
            'nojsoncallback': '1',
            'photoset_id': photoset_id,
            'photo_id': photo_id,
            'method': 'flickr.photosets.addPhoto'
        }

        return self.call(requests.post, self.rest_url, params=params,
                         auth=self.oauth)

def create_photoset(self, title, primary_photo_id, description=None):
        params = {
            'format': 'json',
            'nojsoncallback': '1',
            'title': title,
            'description': description,
            'method': 'flickr.photosets.create',
            'primary_photo_id': primary_photo_id
        }

        params = {k: v for k, v in params.items() if v is not None}

        return self.call(requests.get, self.rest_url, params=params,
                         auth=self.oauth)


def start():
    if plug.options.get('user_id', None) is None:
        return DriverError("You must set a Flickr user ID in order to use"
                           " the Flickr driver")


    # Clean the root
    global root
    root = plug.options['root']
    if root.startswith('/'):
        root = root[1:]
    if root.endswith('/'):
        root = root[:-1]

    onitu_client_id = plug.options['onitu_client_id']
    onitu_client_secret = plug.options['onitu_client_secret']

    global flickr
    flickr = Flickr(onitu_client_id, onitu_client_secret,
                    plug.options['oauth_token'],
                    plug.options['oauth_token_secret'], root)

    plug.listen()
