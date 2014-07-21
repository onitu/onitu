import os
import sys
import threading
from StringIO import StringIO
import time

import dropbox
from dropbox.session import DropboxSession
from dropbox.client import DropboxClient

from onitu.plug import Plug

# Onitu has a unique set of App key and secret to identify it.
ONITU_APP_KEY = "6towoytqygvexx3"
ONITU_APP_SECRET = "90hsd4z4d8eu3pp"
ONITU_ACCESS_TYPE = "dropbox"  # full access to user's Dropbox (may change)

# # Onitu has a unique set of App key and secret to identify it.
# ONITU_APP_KEY = "38jd72msqedx5n9"
# ONITU_APP_SECRET = "g4favy0bgjstt2w"

plug = Plug()
dropbox_client = None

# drop = None

# ########################################################################
# class DropboxDriver :
#     """
#     Dropbox object that can access your dropbox folder,
#     as well as download and upload files to dropbox
#     """
#     cursor = None
    
#     def __init__(self, path='/'):
#         """Constructor"""
#         self.base_path = os.path.dirname(os.path.abspath(__file__))
#         self.path = path
#         self.client = None
#         self.session = None
#         self.access_type = "dropbox"
#         self.client_tokens_file = plug.options['token_file']
#         self.chunked_file_size = 25600000 # 25Mo
        
#         self.session = dropbox.session.DropboxSession(plug.options["key"],
#                                                       plug.options["secret"],
#                                                       self.access_type)
        
#         # Try to get a saved token, or get and store a new token with first_connect()
#         try :
#             with open(self.client_tokens_file) as token_file:
#                 token_key, token_secret = token_file.read().split('|')
#         except (IOError, ValueError) as e :
#             token_key, token_secret = self.first_connect()
            
#         self.session.set_token(token_key, token_secret)
#         self.client = dropbox.client.DropboxClient(self.session)
            
#     def first_connect(self):
#         """
#         Connect, authenticate with dropbox and store client tokens
#         """
       
#         request_token = self.session.obtain_request_token()
 
#         url = self.session.build_authorize_url(request_token)
#         msg = "Open %s and allow Onitu to use your dropbox."
#         print msg % url
#         while not ('access_token' in locals() or 'access_token' in globals()) :
#             try :
#                 access_token = self.session.obtain_access_token(request_token)
#             except (dropbox.rest.ErrorResponse) as e:
#                 time.sleep(2)

#         with open(self.client_tokens_file, 'w') as token_file:
#             token_file.write("%s|%s" % (access_token.key, access_token.secret))
   
#         return access_token.key, access_token.secret
 
#     def download_chunk(self, metadata, offset, size):
#         """
#         Request to get a chunk of a file
#         """

#         if not filename.startswith("/files/dropbox/") :
#             filename = "/files/dropbox/"+metadata.filename

#         url, params, headers = self.client.request(filename, {}, method='GET', content_server=True)
#         headers['Range'] = 'bytes=' + str(offset)+"-"+str(offset+size)
#         f = self.client.rest_client.request("GET", url, headers=headers, raw_response=True)
#         return f.read()

#     def upload_chunk(self, metadata, offset, chunk):
#         uploader = self.client.get_chunked_uploader(StringIO.StringIO(chunk), metadata.size)

#         uploader.offset = offset
#         uploader.upload_chunked(len(chunk))
        
#         res = uploader.finish(metadata.filename)

#         return res

#     def get_account_info(self):
#         """
#         Returns the account information, such as user's display name,
#         quota, email address, etc
#         """
#         return self.client.account_info()
    
#     def list_folder(self, folder=None):
#         """
#         Return a dictionary of information about a folder
#         """
#         if folder:
#             folder_metadata = self.client.metadata(folder)
#         else:
#             folder_metadata = self.client.metadata("/")
#         return folder_metadata

#     def delete_file(self, filename):
#         try:
#             self.client.file_delete(filename)
#             return True
#         except:
#             return False

#     def create_dir(self, dirname):
#         try:
#             self.client.file_create_folder(dirname)
#             return True
#         except:
#             return False

#     def update_metadata(self, metadata):
#         file_metadata = self.client.metadata(metadata.filename)
#         if (file_metadata["revision"]):
#             metadata.revision = file_metadata["revision"]
#             metadata.size = file_metadata["bytes"]
#             plug.update_file(metadata)

#     def change_watcher(self):
#         delta = self.client.delta(self.cursor)
#         # print delta
#         for f in delta["entries"]:
#             if f[0][0] == '/':
#                 f[0] = f[0][1:]
#             metadata = plug.get_metadata(f[0])
#             metadata.size = f[1]["bytes"]
#             metadata.revision = f[1]["revision"]
#             plug.update_file(metadata)
#         if delta['has_more']:
#             self.change_watcher()
#         else:
#             threading.Timer(plug.options["changes_timer"], self.change_watcher).start()
 
# @plug.handler()
# def get_chunk(metadata, offset, size):
#     drop = DropboxDriver()
#     return drop.download_chunk(metadata.filename, offset, size)

# @plug.handler()
# def upload_chunk(metadata, offset, chunk):
#     drop = DropboxDriver()
#     return drop.upload_chunk(metadata, offset, chunk)

# @plug.handler()
# def end_upload(metadata):
#     drop = DropboxDriver()
#     drop.update_metadata(metadata)
#     print drop

def connect_client():
    """Helper function to connect to Dropbox via the API, using access token
    keys to authenticate Onitu."""
    global dropbox_client
    global plug
    plug.logger.debug("Attempting Dropbox connection using Onitu credentials")
    sess = DropboxSession(ONITU_APP_KEY,
                          ONITU_APP_SECRET,
                          ONITU_ACCESS_TYPE)
    # Use the OAuth access token previously retrieved by the user and typed
    # into Onitu configuration.
    sess.set_token(plug.options['access_key'], plug.options['access_secret'])
    dropbox_client = DropboxClient(sess)
    plug.logger.debug("Dropbox connection with Onitu credentials successful")
    return dropbox_client


@plug.handler()
def get_chunk(metadata, offset, size):
    global dropbox_client
    global plug
    filename = root_prefixed_filename(metadata.filename)
    if not filename.startswith("/files/dropbox/"):
        filename = "/files/dropbox/" + filename
    # content_server = True is required to let us access to file contents,
    # not only metadata
    url, params, headers = dropbox_client.request(filename,
                                                  method="GET",
                                                  content_server=True)
    # Using the 'Range' HTTP Header for offseting.
    headers['Range'] = "bytes={}-{}".format(offset, offset+(size-1))
    plug.logger.debug("Getting chunk of size {} from file {}"
                      " from offset {} to {}".format(
            size, filename, offset, offset+(size-1)
            ))
    chunk = dropbox_client.rest_client.request("GET",
                                               url,
                                               headers=headers,
                                               raw_response=True)
    plug.logger.debug("Getting chunk of size {} from file {}"
                      " from offset {} to {} - Done".format(
            size, filename, offset, offset+(size-1)
            ))
    return chunk.read()


def root_prefixed_filename(filename):
    global plug
    name = plug.options['root']
    if not name.endswith('/'):
        name += '/'
    name += filename
    return name


@plug.handler()
def upload_chunk(metadata, offset, chunk):
    global dropbox_client
    filename = root_prefixed_filename(metadata.filename)
    buff = StringIO(chunk)
    # Get the upload id of this file. If we don't have it, e.g. since it's
    # the first chunk of this upload, the `get` method permits not to raise a
    # KeyError.
    up_id = metadata.extra.get('upload_id', None)
    plug.logger.debug("Uploading chunk of size {}"
                      " to file {} at offset {} - Upload ID: {}".format(
            len(chunk), filename, offset, up_id
            ))
    # upload_chunk returns a tuple containing the offset and the upload ID of
    # this upload. The offset isn't very useful
    (_, up_id) = dropbox_client.upload_chunk(file_obj=buff,
                                             length=len(chunk),
                                             offset=offset,
                                             upload_id=up_id)
    plug.logger.debug("Uploading chunk of size {}"
                      " to file {} at offset {} - Done".format(
            len(chunk), filename, offset
            ))
    plug.logger.debug("Storing upload ID {} in metadata".format(up_id))
    metadata.extra['upload_id'] = up_id
    metadata.write()


@plug.handler()
def end_upload(metadata):
    global dropbox_client

    filename = root_prefixed_filename(metadata.filename)
    # Note the difference between dropbox_client (the global variable), and
    # dropbox.client, the access to the dropbox.client submodule
    path = "/commit_chunked_upload/{}/{}".format(
        dropbox_client.session.root,
        dropbox.client.format_path(filename)
        )
    plug.logger.debug("Ending upload using path {}".format(path))
    up_id = metadata.extra.get('upload_id', None)
    # At this point we should have the upload ID no matter what
    if up_id is None:
        raise DriverError("No upload ID for {}".format(filename))
    params = dict(
        overwrite = True,
        upload_id = up_id
        )
    url, params, headers = dropbox_client.request(path,
                                               params,
                                               content_server=True)
    dropbox_client.rest_client.POST(url, params, headers)
    plug.logger.debug("Ending upload using path {} - Done".format(path))
    plug.logger.debug("Removing upload ID '{}' from metadata".format(up_id))
    metadata.extra['upload_id'] = None
    metadata.write()


def start(*args, **kwargs):
    client = connect_client()
    plug.listen()
