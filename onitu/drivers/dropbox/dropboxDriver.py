import dropbox
import os
import sys
import requests
import threading

from dropbox import rest
from configobj import ConfigObj

# from onitu.api import Plug

# plug = Plug()
 
########################################################################
class DropboxDriver :
    """
    Dropbox object that can access your dropbox folder,
    as well as download and upload files to dropbox
    """
    cursor = None
    
    #----------------------------------------------------------------------
    def __init__(self, path='/'):
        """Constructor"""
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.path = path
        self.client = None
        self.session = None
        self.access_type = "dropbox"
        self.client_tokens_file = "client_tokens"
        self.chunked_file_size = 25600000 # 25Mo
        
        config_path = os.path.join(self.base_path, "config.ini")
        if os.path.exists(config_path):
            try:
                cfg = ConfigObj(config_path)
            except IOError:
                print "ERROR opening config file!"
                sys.exit(1)
            self.cfg_dict = cfg.dict()
        else:
            print "ERROR: config.ini not found! Exiting!"
            sys.exit(1)
                 
        self.session = dropbox.session.DropboxSession(self.cfg_dict["key"],
                                                      self.cfg_dict["secret"],
                                                      self.access_type)
 
        # Try to get a saved token, or get and store a new token with first_connect()
        try :
            with open(self.client_tokens_file) as token_file:
                token_key, token_secret = token_file.read().split('|')
        except (IOError, ValueError) as e :
            token_key, token_secret = self.first_connect()
 
        self.session.set_token(token_key, token_secret)
        self.client = dropbox.client.DropboxClient(self.session)
        self.change_watcher()
 
    #----------------------------------------------------------------------
    def first_connect(self):
        """
        Connect, authenticate with dropbox and store client tokens
        """
       
        request_token = self.session.obtain_request_token()
 
        url = self.session.build_authorize_url(request_token)
        msg = "Open %s and allow Onitu to use your dropbox."
        print msg % url
        raw_input("Press enter to continue")
        access_token = self.session.obtain_access_token(request_token)
 
        with open(self.client_tokens_file, 'w') as token_file:
            token_file.write("%s|%s" % (access_token.key, access_token.secret))
   
        return access_token.key, access_token.secret
 
    #----------------------------------------------------------------------
    def download_file(self, filename, outDir=None):
        """
        Download either the file passed to the class or the file passed
        to the method
        """
 
        fname = filename
        f, metadata = self.client.get_file_and_metadata("/" + fname)
 
        if metadata['bytes'] > self.chunked_file_size :
            return self.download_big_file(fname)

        if outDir:
            dst = os.path.join(outDir, fname)
        else:
            dst = fname

 
        with open(fname, "wb") as fh:
            fh.write(f.read())
 
        return dst, metadata
 
    #----------------------------------------------------------------------
    def download_big_file(self, filename, outDir=None):
       
        fname = filename
        metadata = self.client.metadata(fname)
        size = metadata['bytes']

        if outDir:
            dst = os.path.join(outDir, fname)
        else:
            dst = fname

        endchunk = self.chunked_file_size
        startchunk = 0
        with open(fname, "wb") as fh:
            try:
                while startchunk < size:
                    print "New chunk: ", startchunk, " - ", endchunk
                    url, params, headers = self.client.request("/files/dropbox/"+fname, {}, method='GET', content_server=True)
                    headers['Range'] = 'bytes=' + str(startchunk)+"-"+str(endchunk)
                    f = self.client.rest_client.request("GET", url, headers=headers, raw_response=True)
                    fh.write(f.read())
                    endchunk += self.chunked_file_size
                    startchunk += self.chunked_file_size + 1
                    if endchunk > size:
                        endchunk = size
                    
            except Exception, e:
                print "ERROR: ", e

        return dst, metadata
 
    #----------------------------------------------------------------------
    def download_chunk(self, filename, offset, size):
        filename = "/files/dropbox"+filename
        print "New chunk: ", offset, " - ", offset+size
        url, params, headers = self.client.request("/files/dropbox/"+fname, {}, method='GET', content_server=True)
        headers['Range'] = 'bytes=' + str(offset)+"-"+str(offset+size)
        f = self.client.rest_client.request("GET", url, headers=headers, raw_response=True)
        return f.read()
    #----------------------------------------------------------------------
    def upload_file(self, filename):
        """
        Upload a file to dropbox, returns file info dict
        """
        path = os.path.join(self.path, filename)
 
        if os.path.getsize(filename) > self.chunked_file_size :
            return self.upload_big_file(filename)
 
        try:
            with open(filename,'rb') as fh:
                res = self.client.put_file(path, fh)
                print "uploaded: ", res
        except Exception, e:
            print "ERROR: ", e
 
        return res
 
    #----------------------------------------------------------------------
    def upload_big_file(self, filename):
        """
        Upload a file to dropbox, returns file info dict
        """
        size = os.path.getsize(filename)
        with open(filename, 'rb') as fh:
            uploader = self.client.get_chunked_uploader(fh, size)
            print "uploading: ", size
       
            while uploader.offset < size:
                try:
                    uploader.upload_chunked(1024000)
                except rest.ErrorResponse, e:
                    pass
                   
            res = uploader.finish(os.path.join(self.path, filename))
 
        return res
           
    #----------------------------------------------------------------------
    def get_account_info(self):
        """
        Returns the account information, such as user's display name,
        quota, email address, etc
        """
        return self.client.account_info()
 
    #----------------------------------------------------------------------
    def list_folder(self, folder=None):
        """
       Return a dictionary of information about a folder
       """
        if folder:
            folder_metadata = self.client.metadata(folder)
        else:
            folder_metadata = self.client.metadata("/")
        return folder_metadata

    #----------------------------------------------------------------------
    def change_watcher(self):
        delta = self.client.delta(self.cursor)
        print delta
        for f in delta.entries:
            metadata = plug.get_metadata(f[0])
            metadata.size = f[1]["bytes"]
            metadata.revision = f[1]["revision"]
            plug.update_file(metadata)
        if delta['has_more']:
            self.change_watcher()
        else:
            threading.Timer(600, self.change_watcher).start()
 
# @plug.handler()
# def get_chunk(filename, offset, size):
#     return drop.download_chunk(filename, offset, size)

# @plug.handler()
# def start_upload(metadata):

# @plug.handler()
# def upload_chunk(filename, offset, chunk):
#     with open(filename, 'rb') as fd:
#         return self.client.upload_chunk(fd, filename.size, offset)

if __name__ == "__main__":
    drop = DropboxDriver()
 
#    print drop.list_folder()
print drop.get_account_info()
# drop.download_file("Premiers pas.pdf")
# drop.upload_file("SUPERHOT-LINUX.zip")
# drop.download_file("SUPERHOT-LINUX.zip")
