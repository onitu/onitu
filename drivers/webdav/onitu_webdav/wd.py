import os
import threading
import datetime

from io import BytesIO

import webdav.client as wc

from onitu.plug import Plug, ServiceError
from onitu.escalator.client import EscalatorClosed
from onitu.utils import u, b

TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S %Z'
plug = Plug()
events_to_ignore = set()


def get_WEBDAV_client(hostname, username, password):
    options = {
        'webdav_hostname': hostname,
        'webdav_login': username,
        'webdav_password': password,
    }
    webd = wc.Client(options)
    return webd


def get_WEBDAV_client_from_plug():
    hostname = plug.options['hostname']
    username = plug.options['username']
    password = plug.options['password']
    return get_WEBDAV_client(
        hostname,
        username,
        password
    )


def create_dirs(webd, path):
    root = ''
    dirs = path.split('/')
    for d in dirs[1:]:
        p = u'/'.join([root, d])
        webd.mkdir(b(p))
        root = p


@plug.handler()
def delete_file(metadata):
    webd = get_WEBDAV_client_from_plug()
    plug.logger.debug(u"delete file: {}", metadata.path)
    webd.clean(b(metadata.path))


@plug.handler()
def get_file(metadata):
    webd = get_WEBDAV_client_from_plug()
    try:
        plug.logger.debug(u"get file, metadata {}", metadata.path)
        buff = BytesIO()
        webd.download_to(buff, b(metadata.path))
        return buff.getvalue()

    except Exception as e:
        raise ServiceError(
            u"Error getting file '{}': {}".format(metadata.path, e)
        )


@plug.handler()
def start_upload(metadata):
    webd = get_WEBDAV_client_from_plug()
    plug.logger.debug(u"start upload: {}", metadata.path)
    events_to_ignore.add(metadata.path)
    create_dirs(webd, os.path.dirname(metadata.path))


@plug.handler()
def upload_file(metadata, content):
    webd = get_WEBDAV_client_from_plug()
    try:
        plug.logger.debug(u"upload file, metadata {}", metadata.path)
        buff = BytesIO(content)
        webd.upload_from(buff, b(metadata.path))
    except Exception as e:
        raise ServiceError(
            u"Error writting file '{}': {}".format(metadata.path, e)
        )


@plug.handler()
def end_upload(metadata):
    webd = get_WEBDAV_client_from_plug()
    try:
        plug.logger.debug(u"end upload, metadata {}", metadata.path)
        infos = webd.info(b(metadata.path))
        metadata.extra['revision'] = infos['modified']
        metadata.write()

    except Exception as e:
        raise ServiceError(
            u"Error while updating metadata on file '{}': {}".format(
                metadata.path, e)
        )
    finally:
        if metadata.path in events_to_ignore:
            events_to_ignore.remove(metadata.path)


@plug.handler()
def move_file(old_metadata, new_metadata):
    webd = get_WEBDAV_client_from_plug()
    webd.move(
        remote_path_from=b(old_metadata.path),
        remote_path_to=b(new_metadata.path)
    )


def update_file(metadata, f, infos):
    try:
        metadata.size = int(infos['size'])
        metadata.extra['revision'] = infos['modified']
        metadata.write()
        plug.update_file(metadata)
    except Exception as e:
        raise ServiceError(
            u"Error updating file '{}': {}".format(metadata.path, e)
        )


class CheckChanges(threading.Thread):

    def __init__(self, timer, webdav):
        super(CheckChanges, self).__init__()
        self.stop = threading.Event()
        self.timer = timer
        self.webdav = webdav
        for folder in plug.folders_to_watch:
            create_dirs(self.webdav, folder.path)

    def check_folder(self, path):
        if path.endswith('/'):
            path = path[:-1]
        plug.logger.debug(u"check folder: path {}", path)

        try:
            filelist = self.webdav.list(b(path))
        except Exception as e:
            raise ServiceError(
                u"Error listing file in '{}': {}".format(path, e)
            )
        plug.logger.debug(u"filelist {}", filelist)

        # list all the files of a folder
        files = []

        for f in filelist:
            f = u(f)
            filepath = u'/'.join([path, f])
            plug.logger.debug(u"filepath: {}", filepath)
            try:
                if self.webdav.is_dir(b(filepath)):
                    sub_files = self.check_folder(filepath)
                    for sub_file in sub_files:
                        files.append(sub_file)
                else:
                    files.append(filepath)
                    infos = self.webdav.info(b(filepath))
                    plug.logger.debug(u'infos {}: {}', filepath, infos)
                    metadata = plug.get_metadata(filepath)
                    if metadata is None:
                        plug.logger.debug(u"ignore file {}", filepath)
                        continue
                    mtime_onitu = metadata.extra.get(
                        'revision',
                        None
                    )
                    if mtime_onitu is None:
                        mtime_onitu = datetime.datetime.min
                    else:
                        mtime_onitu = datetime.datetime.strptime(
                            mtime_onitu, TIMESTAMP_FMT
                        )
                    mtime_local = datetime.datetime.strptime(
                        infos['modified'], TIMESTAMP_FMT
                    )
                    if mtime_local > mtime_onitu:
                        update_file(metadata, f, infos)
            except wc.WebDavException as exception:
                plug.logger.debug(
                    (u"Exception while the informations about a file "
                     "were fetched: {}"), exception
                )
                continue
        return files

    def delete_files(self, folder, files):
        old_files = plug.list(folder).keys()
        plug.logger.debug(u"old_files {}", old_files)
        for f in old_files:
            filepath = u'/'.join([folder.path, f])
            plug.logger.debug(u"filepath delete: {}", filepath)
            if filepath in events_to_ignore:
                continue
            if filepath not in files:
                metadata = plug.get_metadata(filepath)
                plug.delete_file(metadata)

    def run(self):
        while not self.stop.isSet():
            try:
                for folder in plug.folders_to_watch:
                    files = self.check_folder(folder.path)
                    plug.logger.debug(u"list of files {}", files)
                    self.delete_files(folder, files)
            except EscalatorClosed:
                # We are closing
                return
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    webd = get_WEBDAV_client_from_plug()
    timer = plug.options['changes_timer']
    # Launch the changes detection
    check_changes = CheckChanges(timer, webd)
    check_changes.daemon = True
    check_changes.start()

    plug.listen()
