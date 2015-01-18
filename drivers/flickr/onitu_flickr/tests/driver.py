import os
import hashlib
from io import BytesIO

from tests.utils import driver
from onitu.utils import get_random_string
from onitu_flickr.flickr_driver import API_KEY, API_SECRET, FlickrHandler


class Driver(driver.Driver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):
        self._root = get_random_string(10)
        self.root_id = ''  # Cannot set that now

        if 'key' not in options:
            options['oauth_token'] = os.environ['ONITU_FLICKR_TOKEN']
        if 'secret' not in options:
            options['oauth_token_secret'] = os.environ['ONITU_FLICKR_SECRET']
        if 'changes_timer' not in options:
            options['changes_timer'] = 10
        self.handler = FlickrHandler(API_KEY, API_SECRET,
                                     options['oauth_token'],
                                     options['oauth_token_secret'])
        super(Driver, self).__init__(u'flickr',
                                     *args,
                                     **options)

    @property
    def root(self):
        return self._root

    def close(self):
        self.handler.flickr_api.photosets.delete(photoset_id=self.root_id)

    def mkdir(self, subdirs):
        photosetID = self.handler.get_photoset_ID(subdirs)
        ppid = "14592381294"  # TODO: Fix that ?
        self.handler.flickr_api.photosets.create(photoset_id=photosetID,
                                                 primary_photo_id=ppid)

    def rmdir(self, path):
        photosetID = self.handler.get_photoset_ID(path)
        self.handler.flickr_api.photosets.delete(photoset_id=photosetID)

    def write(self, filename, content):
        data = BytesIO(content)
        self.handler.upload_photo_in_photoset(filename, data, self.root)

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def exists(self, filename):
        extra = "original_format"
        setID = self.root_id
        rsp = self.handler.flickr_api.photosets.getPhotos(photoset_id=setID,
                                                          extras=extra)
        photos = rsp.find('photoset').findall('photo')
        for photo in photos:
            if photo.attrib['title'] == filename:
                return True
        return False

    def unlink(self, filename):
        photoID = self.handler.get_photo_ID(filename, self.root_id)
        self.handler.flickr_api.photos.delete(photo_id=photoID)

    def rename(self, source, target):
        photoID = self.handler.get_photo_ID(source, self.root_id)
        self.handler.flickr_api.setMeta(photo_id=photoID, title=target)

    def checksum(self, filename):
        photoID = self.handler.get_photo_ID(filename, self.root_id)
        data = self.handler.download_photo_content(photoID)
        return hashlib.md5(data.read()).hexdigest()


class DriverFeatures(driver.DriverFeatures):
    del_file_to_onitu = False
    move_file_to_onitu = False

    copy_directory_from_onitu = False
    copy_directory_to_onitu = False
    del_directory_from_onitu = False
    del_directory_to_onitu = False
    move_directory_from_onitu = False
    move_directory_to_onitu = False

    copy_tree_from_onitu = False
    copy_tree_to_onitu = False
    del_tree_from_onitu = False
    del_tree_to_onitu = False
    move_tree_from_onitu = False
    move_tree_to_onitu = False

    detect_new_file_on_launch = True
    detect_del_file_on_launch = False
    detect_moved_file_on_launch = False
