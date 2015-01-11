import os
import threading
import datetime

from io import BytesIO

import webdav.client as wc

from onitu.plug import Plug, ServiceError
from onitu.escalator.client import EscalatorClosed
from onitu.utils import u

TIMESTAMP_FMT = '%a, %d %b %Y %H:%M:%S %Z'
plug = Plug()
webd = None
events_to_ignore = set()


def create_dirs(path):
    plug.logger.debug("create dirs: {}", path)
    root = ''
    dirs = path.split('/')
    for d in dirs[1:]:
        p = '/'.join([root, d])
        plug.logger.debug(p)
        webd.mkdir(p)
        root = p


@plug.handler()
def delete_file(metadata):
    plug.logger.debug("delete file: {}", metadata.path)
    webd.unpublish(metadata.path)


@plug.handler()
def get_file(metadata):
    try:
        plug.logger.debug("get file, metadata {}", metadata.path)
        buff = BytesIO()
        webd.download_to(buff, metadata.path)
        return buff.getvalue()

    except Exception as e:
        raise ServiceError(
            "Error getting file '{}': {}".format(metadata.path, e)
        )


@plug.handler()
def start_upload(metadata):
    plug.logger.debug("start upload: {}", metadata.path)
    events_to_ignore.add(metadata.path)
    create_dirs(os.path.dirname(metadata.path))


@plug.handler()
def upload_file(metadata, content):
    try:
        plug.logger.debug("upload file, metadata {}", metadata.path)
        buff = BytesIO(content)
        webd.upload_from(buff, metadata.path)
    except Exception as e:
        raise ServiceError(
            "Error writting file '{}': {}".format(metadata.path, e)
        )


@plug.handler()
def end_upload(metadata):
    try:
        plug.logger.debug("end upload, metadata {}", metadata.path)
        infos = webd.info(metadata.path)
        metadata.extra['revision'] = infos['modified']
        metadata.write()

    except Exception as e:
        raise ServiceError(
            "Error while updating metadata on file '{}': {}".format(
                metadata.path, e)
        )
    finally:
        if metadata.path in events_to_ignore:
            events_to_ignore.remove(metadata.path)


def update_file(metadata, f, infos):
    try:
        metadata.size = int(infos['size'])
        metadata.extra['revision'] = infos['modified']
        metadata.write()
        plug.update_file(metadata)
    except Exception as e:
        raise ServiceError(
            "Error updating file '{}': {}".format(metadata.path, e)
        )


class CheckChanges(threading.Thread):

    def __init__(self, timer, webdav):
        super(CheckChanges, self).__init__()
        self.stop = threading.Event()
        self.timer = timer
        self.webdav = webdav

    def check_folder(self, path):
        if path.endswith('/'):
            path = path[:-1]
        plug.logger.debug("check folder: path {}", path)
        try:
            filelist = self.webdav.list(path)
        except Exception as e:
            raise ServiceError(
                "Error listing file in '{}': {}".format(path, e)
            )

        plug.logger.debug("filelist {}", filelist)
        for f in filelist:
            filepath = u('/'.join([path, f]))

            if self.webdav.is_dir(filepath):
                self.check_folder(filepath)
            else:
                infos = self.webdav.info(filepath)
                plug.logger.debug('infos: {}', infos)
                metadata = plug.get_metadata(filepath)
                if metadata is None:
                    plug.logger.debug("ignore file {}", filepath)
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

    def run(self):
        while not self.stop.isSet():
            try:
                for folder in plug.folders_to_watch:
                    self.check_folder(folder.path)
            except EscalatorClosed:
                # We are closing
                return
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    hostname = plug.options['hostname']
    username = plug.options['username']
    password = plug.options['password']
    timer = plug.options['changes_timer']

    global prefix
    prefix = hostname

    global webd
    options = {
        'webdav_hostname': hostname,
        'webdav_login': username,
        'webdav_password': password,
    }
    webd = wc.Client(options)

    # Launch the changes detection
    check_changes = CheckChanges(timer, webd)
    check_changes.daemon = True
    check_changes.start()

    plug.listen()
