import cStringIO
import requests
import hashlib

from xml.etree.ElementTree import fromstring, ElementTree
from requests_toolbelt import MultipartEncoder
from requests_oauthlib import OAuth1

from onitu.plug import Plug, ServiceError

plug = Plug()

# ############################## OAUTH ######################################


class Flickr():
    def __init__(self, client_key, client_secret, oauth_token,
                 oauth_token_secret, root):
        self.client_key = client_key
        self.client_secret = client_secret
        self.oauth_token = oauth_token
        self.oauth_token_secret = oauth_token_secret
        self.root = root

        self.oauth = OAuth1(client_key,
                            client_secret=client_secret,
                            resource_owner_key=oauth_token,
                            resource_owner_secret=oauth_token_secret)

        self.rest_url = 'https://api.flickr.com/services/rest/'
        self.upload_url = 'https://up.flickr.com/services/upload/'
        self.replace_url = 'https://up.flickr.com/services/replace/'
        self.onitu_tag = 'ONITU_TAG_DO_NOT_REMOVE/'

        self.load_base_params().update({'method': 'flickr.test.login'})
        self.user_id = self.call('GET', self.rest_url,
                                 self.base_params).json()['user']['id']

# ############################## UTILS ######################################

    def create_tag(self, metadata):
        return self.onitu_tag + self.root + '/' + hashlib.md5(
            metadata.filename + str(metadata.size)).hexdigest()

    def load_base_params(self):
        self.base_params = {
            'format'         : 'json',
            "nojsoncallback" : "1"
            }
        return self.base_params

    def load_tag_id(self, metadata):
        if 'tag_id' in metadata.extra:
            return metadata.extra['tag_id']
        return self.get_tag_id(self.load_photo_id(metadata),
                               metadata.extra['tag'])

    def load_photo_id(self, metadata):
        if 'id' in metadata.extra:
            return metadata.extra['id']
        return self.search_file(metadata)

    def check_error(self, func_name, req):
        if req.status_code != 200:
            raise ServiceError(
                '{}: Status code {} received'.format(
                    func_name, req.status_code
                    )
                )

    def do_upload(self, url, content, params=None):
        '''Performs a file upload to the given URL with
        the given parameters, signed with OAuth.'''

        # work-around for Flickr expecting 'photo' to be excluded
        # from the oauth signature:
        #   1. create a dummy request without 'photo'
        #   2. create real request and use auth headers from the dummy one
        dummy_req = requests.Request('POST', url, data=params,
                                     auth=self.oauth)

        prepared = dummy_req.prepare()
        headers = prepared.headers

        fileobj = cStringIO.StringIO(content)
        params['photo'] = (params['title'], fileobj)

        m = MultipartEncoder(fields=params)
        auth = {'Authorization': headers.get('Authorization'),
                'Content-Type' : m.content_type}
        req = requests.post(url, data=m, headers=auth)

        # check the response headers / status code.
        self.check_error('do_upload', req)
        return req

    def search_file(self, metadata):
        ''' return None if no file or many files are found.
        return file id otherwise '''
        tag = self.create_tag(metadata)

        self.load_base_params().update({
                'user_id'        : self.user_id,
                'method'         : 'flickr.photos.search',
                'tags'           : tag
                })

        r = self.call('GET', self.rest_url, self.base_params)
        self.check_error('search_file', r)
        json = r.json()

        res_nb = len(json['photos']['photo'])
        if (res_nb == 0) or (res_nb > 1):
            return None
        else:
            return json['photos']['photo'][0]['id']

    def call(self, method, url, params, content=None):
        # Clean params
        for k in params.keys():
            if params[k] is None:
                del params[k]

        if method.lower() == 'get':
            r = requests.get(url, params=params, auth=self.oauth)
        elif method.lower() == 'upload':
            r = self.do_upload(url, content, params=params)
        else:
            r = requests.post(url, params=params, auth=self.oauth)

        # clean base_params
        self.load_base_params()

        return r

# ############################## FLICKR ######################################

    def upload_file(self, metadata, content):

        photo_id = self.load_photo_id(metadata)
        tag = metadata.extra['tag']
        title = metadata.filename
        self.load_base_params().update({
                'photo_id'        : photo_id,  # only used for replacement
                'title'           : title,
                'description'     : 'Uploaded by onitu',
                'tags'            : tag,
                'is_public'       : '0',
                'is_friend'       : '0',
                'is_family'       : '0',
                'safety_level'    : '1',
                'hidden'          : '1'
                })

        if photo_id:
            print 'replace'
        url = self.replace_url if photo_id else self.upload_url
        r = self.call('UPLOAD', url, self.base_params, content).content

        tree = ElementTree(fromstring(r)).getroot()
        photo_id = tree.find('photoid').text

        metadata.extra['id'] = photo_id
        metadata.write()

    def get_file(self, metadata):
        ''' return nothing '''
        photo_id = self.load_photo_id(metadata)
        if photo_id:
            self.load_base_params().update({
                    'method'         : 'flickr.photos.getSizes',
                    'photo_id'       : photo_id
                    })

            r = self.call('GET', self.rest_url, self.base_params)
            self.check_error('get_photo', r)
            # 5 = Original size
            url = r.json()['sizes']['size'][5]['source']
            r = requests.get(url, auth=self.oauth)
            self.check_error('get_photo', r)
            return r.content

    def delete_file(self, metadata):
        ''' return nothing '''

        photo_id = self.load_photo_id(metadata)
        if photo_id:
            self.load_base_params().update({
                    'method'         : 'flickr.photos.delete',
                    'photo_id'       : photo_id
                    })

            r = self.call('GET', self.rest_url, self.base_params)
            self.check_error('delete_file', r)

    def get_tag_id(self, photo_id, tag_name):
        try:
            tag = self.get_file_info(photo_id)['photo']['tags']['tag']
        except KeyError:
            global plug
            plug.logger.warning(
                "get_tag_id: Cannot find tag id of tag '{}'".format(tag_name))
            return None
        i = 0
        while (tag[i]):
            if tag[i]['raw'] == tag_name:
                return tag[i]['id']
            i += 1
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

    def get_file_info(self, photo_id):
        ''' Return a json with photo infos '''

        self.load_base_params().update({
                'method'         : 'flickr.photos.getInfo',
                'photo_id'       : photo_id
                })
        r = self.call('GET', self.rest_url, self.base_params)
        self.check_error('get_file_info', r)
        return r.json()

    def remove_tag(self, tag_id):
        ''' Return nothing '''

        self.load_base_params().update({
                'method'         : 'flickr.photos.removeTag',
                'tag_id'         : tag_id
                })
        r = self.call('POST', self.rest_url, self.base_params)
        self.check_error('remove_tag', r)

    def add_tags(self, photo_id, tags):
        ''' Return nothing '''

        self.load_base_params().update({
                'method'         : 'flickr.photos.addTags',
                'photo_id'       : photo_id,
                'tags'           : tags
                })
        r = self.call('POST', self.rest_url, self.base_params)
        self.check_error('add_tags', r)

    def rename_file(self, photo_id, title):
        ''' Return nothing '''

        self.load_base_params().update({
                'method'         : 'flickr.photos.setMeta',
                'photo_id'       : photo_id,
                'title'          : title,
                'description'    : 'Uploaded by onitu'  # required parameter
                })
        r = self.call('POST', self.rest_url, self.base_params)
        self.check_error('rename_file', r)

# ############################# PHOTOSETS ###################################

    def list_photosets(self):
        self.load_base_params().update({
                'user_id'        : self.user_id,
                'method'         : 'flickr.photosets.getList'
                })

        return self.call('GET', self.rest_url, self.base_params)

    def create_photoset(self, title, primary_photo_id, description=None):
        self.load_base_params().update({
                'title'           : title,
                'description'     : description,
                'method'          : 'flickr.photosets.create',
                'primary_photo_id': primary_photo_id
                })

        return self.call('GET', self.rest_url, self.base_params)


# ############################# ONITU BASIC ###################################


@plug.handler()
def move_file(old_metadata, new_metadata):
    global flickr
    flickr.move_file(old_metadata, new_metadata)


@plug.handler()
def get_file(metadata):
    global flickr
    flickr.get_file(metadata)


@plug.handler()
def start_upload(metadata):
    global flickr
    metadata.extra['tag'] = flickr.create_tag(metadata)


@plug.handler()
def upload_file(metadata, content):
    global flickr
    flickr.upload_file(metadata, content)


@plug.handler()
def delete_file(metadata):
    global flickr
    flickr.delete_file(metadata)


def start():
    global plug

    # Clean the root
    root = plug.options['root']
    if root.startswith('/'):
        root = root[1:]
    if root.endswith('/'):
        root = root[:-1]

    onitu_client_id = "66a1c393c8de67fbeef54bb785375e06"
    onitu_client_secret = "5bfbc7256872d085"

    global flickr
    flickr = Flickr(onitu_client_id, onitu_client_secret,
                    plug.options['oauth_token'],
                    plug.options['oauth_token_secret'], root)

    plug.listen()
