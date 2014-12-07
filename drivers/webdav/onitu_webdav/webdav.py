import os
import threading

import easywebdav

from onitu.plug import Plug, ServiceError
from onitu.escalator.client import EscalatorClosed

plug = Plug()
root = None
webdav = None
prefix = None
events_to_ignore = set()


def create_dirs(webdav, path):
    print "create dirs '{}'".format(path)
    webdav.mkdirs(path)
    # parent_exists = True
    # tmp_path = './'
    # dirs = path.split('/')

    # for d in dirs:
    #     tmp_path = os.path.join(tmp_path, d)

    #     # If the parent exists, we check if the current path exists
    #     if parent_exists is True:
    #         try:
    #             sftp.stat(tmp_path)
    #         # The current path doesn't exists, so we create it
    #         except IOError:
    #             try:
    #                 parent_exists = False
    #                 sftp.mkdir(tmp_path)
    #             except IOError as e:
    #                 raise ServiceError(
    #                     "Error creating dir '{}': {}".format(tmp_path, e)
    #                     )
    #     # If the parent doesn't exist, we can create the current dir without
    #     # check if it exists
    #     else:
    #         try:
    #             sftp.mkdir(tmp_path)
    #         except IOError as e:
    #             raise ServiceError(
    #                 "Error creating dir '{}': {}".format(tmp_path, e)
    #                 )


@plug.handler()
def get_file(metadata):
    try:
        path = '/'.join([root, metadata.filename])
        print "get file path: {}".format(path)
        local_file = "/tmp/{}".format(os.path.basename(metadata.filename))
        webdav.download(path, local_file)
        with open(local_file, 'r') as f:
            data = f.read()
        return data

    except easywebdav.client.OperationFailed as e:
        raise ServiceError(
            "Error getting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def start_upload(metadata):
    print "start upload"
    events_to_ignore.add(metadata.filename)
    create_dirs(webdav, os.path.dirname(metadata.filename))


@plug.handler()
def end_upload(metadata):
    print "end upload"
    return
    try:
        stat_res = sftp.stat(metadata.filename)
        metadata.extra['revision'] = stat_res.st_mtime
        metadata.write()

    except (IOError, OSError) as e:
        raise ServiceError(
            "Error while updating metadata on file '{}': {}".format(
                metadata.filename, e)
        )
    finally:
        if metadata.filename in events_to_ignore:
            events_to_ignore.remove(metadata.filename)


@plug.handler()
def upload_file(metadata, content):
    print "upload file"
    return
    try:
        f = sftp.open(metadata.filename, 'w+')
        f.write(content)
        f.close()
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error writting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def abort_upload(metadata):
    print "abort upload"
    return

    # Temporary solution to avoid problems
    try:
        sftp.remove(metadata.filename)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error deleting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def close():
    print "close"
    return
    sftp.close()
    transport.close()


def update_file(metadata, f):
    try:
        metadata.size = f.size
        metadata.extra['revision'] = f.mtime
        metadata.write()
        plug.update_file(metadata)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error updating file '{}': {}".format(metadata.filename, e)
        )


class CheckChanges(threading.Thread):

    def __init__(self, timer, webdav):
        super(CheckChanges, self).__init__()
        self.stop = threading.Event()
        self.timer = timer
        self.webdav = webdav

    def check_folder(self, path=''):
        path = '/'.join([root, path])
        print "root: {}, path: {}".format(root, path)
        try:
            filelist = self.webdav.ls(path)
        except easywebdav.client.OperationFailed as e:
            raise ServiceError(
                "Error listing file in '{}': {}".format(path, e)
            )

        for f in filelist[1:]:
            print f.name
            filepath = f.name.replace(prefix, "")
            print filepath

            metadata = plug.get_metadata(filepath)
            onitu_rev = metadata.extra.get('revision', 0.)

            if f.mtime > onitu_rev:
                if f.contenttype == "httpd/unix-directory":
                    self.check_folder(filepath)
                else:
                    update_file(metadata, f)

    def run(self):
        while not self.stop.isSet():
            try:
                self.check_folder()
            except EscalatorClosed:
                # We are closing
                return
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    global root

    # Clean the root
    root = plug.options['root']
    if root.endswith('/'):
        root = root[:-1]

    protocol = plug.options['protocol']
    hostname = plug.options['hostname']
    username = plug.options['username']
    password = plug.options['password']
    port = plug.options['port']
    timer = plug.options['changes_timer']

    global prefix
    prefix = "{}://{}:{}{}/".format(
        protocol,
        hostname,
        port,
        root
    )

    print hostname
    print username
    print password
    print protocol
    print port

    global webdav
    webdav = easywebdav.connect(
        hostname,
        username=username,
        password=password,
        protocol=protocol,
        port=port
    )

    # Launch the changes detection
    check_changes = CheckChanges(timer, webdav)
    check_changes.daemon = True
    check_changes.start()

    plug.listen()
