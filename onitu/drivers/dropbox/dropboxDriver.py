import dropbox
import os
import sys
import requests
import threading
import StringIO
import time

from dropbox import rest
from configobj import ConfigObj

from onitu.api import Plug

plug = Plug()
drop = None

########################################################################
class DropboxDriver :
    """
    Dropbox object that can access your dropbox folder,
    as well as download and upload files to dropbox
    """
    cursor = None
    
    def __init__(self, path='/'):
        """Constructor"""
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.path = path
        self.client = None
        self.session = None
        self.access_type = "dropbox"
        self.client_tokens_file = plug.options['token_file']
        self.chunked_file_size = 25600000 # 25Mo
        
        self.session = dropbox.session.DropboxSession(plug.options["key"],
                                                      plug.options["secret"],
                                                      self.access_type)
        
        # Try to get a saved token, or get and store a new token with first_connect()
        try :
            with open(self.client_tokens_file) as token_file:
                token_key, token_secret = token_file.read().split('|')
        except (IOError, ValueError) as e :
            token_key, token_secret = self.first_connect()
            
        self.session.set_token(token_key, token_secret)
        self.client = dropbox.client.DropboxClient(self.session)
            
    def first_connect(self):
        """
        Connect, authenticate with dropbox and store client tokens
        """
       
        request_token = self.session.obtain_request_token()
 
        url = self.session.build_authorize_url(request_token)
        msg = "Open %s and allow Onitu to use your dropbox."
        print msg % url
        while not ('access_token' in locals() or 'access_token' in globals()) :
            try :
                access_token = self.session.obtain_access_token(request_token)
            except (dropbox.rest.ErrorResponse) as e:
                time.sleep(2)

        with open(self.client_tokens_file, 'w') as token_file:
            token_file.write("%s|%s" % (access_token.key, access_token.secret))
   
        return access_token.key, access_token.secret
 
    def download_chunk(self, metadata, offset, size):
        """
        Request to get a chunk of a file
        """

        if not filename.startswith("/files/dropbox/") :
            filename = "/files/dropbox/"+metadata.filename

        url, params, headers = self.client.request(filename, {}, method='GET', content_server=True)
        headers['Range'] = 'bytes=' + str(offset)+"-"+str(offset+size)
        f = self.client.rest_client.request("GET", url, headers=headers, raw_response=True)
        return f.read()

    def upload_chunk(self, metadata, offset, chunk):
        uploader = self.client.get_chunked_uploader(StringIO.StringIO(chunk), metadata.size)

        uploader.offset = offset
        uploader.upload_chunked(len(chunk))
        
        res = uploader.finish(metadata.filename)

        return res

    def get_account_info(self):
        """
        Returns the account information, such as user's display name,
        quota, email address, etc
        """
        return self.client.account_info()
    
    def list_folder(self, folder=None):
        """
        Return a dictionary of information about a folder
        """
        if folder:
            folder_metadata = self.client.metadata(folder)
        else:
            folder_metadata = self.client.metadata("/")
        return folder_metadata

    def delete_file(self, filename):
        try:
            self.client.file_delete(filename)
            return True
        except:
            return False

    def create_dir(self, dirname):
        try:
            self.client.file_create_folder(dirname)
            return True
        except:
            return False

    def update_metadata(self, metadata):
        file_metadata = self.client.metadata(metadata.filename)
        if (file_metadata["revision"]):
            metadata.revision = file_metadata["revision"]
            metadata.size = file_metadata["bytes"]
            plug.update_file(metadata)

    def change_watcher(self):
        delta = self.client.delta(self.cursor)
        # print delta
        for f in delta["entries"]:
            if f[0][0] == '/':
                f[0] = f[0][1:]
            metadata = plug.get_metadata(f[0])
            metadata.size = f[1]["bytes"]
            metadata.revision = f[1]["revision"]
            plug.update_file(metadata)
        if delta['has_more']:
            self.change_watcher()
        else:
            threading.Timer(plug.options["changes_timer"], self.change_watcher).start()
 
@plug.handler()
def get_chunk(metadata, offset, size):
    drop = DropboxDriver()
    return drop.download_chunk(metadata.filename, offset, size)

@plug.handler()
def upload_chunk(metadata, offset, chunk):
    drop = DropboxDriver()
    return drop.upload_chunk(metadata, offset, chunk)

@plug.handler()
def end_upload(metadata):
    drop = DropboxDriver()
    drop.update_metadata(metadata)
    print drop
    
def start(*args, **kwargs):
    plug.initialize(args[0])

    drop = DropboxDriver()

    drop.change_watcher()
    plug.listen()
