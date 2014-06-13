import os
import threading

import paramiko

from stat import S_ISDIR
from onitu.api import Plug, ServiceError

plug = Plug()
root = None
sftp = None
terminated = False
events_to_ignore = set()


def create_dirs(sftp, path):
    dirs = path.split('/')

    tmp_path = "./"
    for d in dirs:
        tmp_path += d + "/"
        try:
            sftp.stat(tmp_path)
        except IOError:
            try:
                sftp.mkdir(tmp_path)
            except IOError as e:
                raise ServiceError(
                    "Error creating dir '{}': {}".format(tmp_path, e)
                )


@plug.handler()
def get_chunk(metadata, offset, size):
    try:
        f = sftp.open(metadata.filename, 'r')
        data = f.readv([(offset, size)])

        for d in data:
            return d

    except (IOError) as e:
        raise ServiceError(
            "Error getting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def start_upload(metadata):

    events_to_ignore.add(metadata.filename)
    create_dirs(sftp, str(os.path.dirname(metadata.filename)))

    try:
        sftp.open(metadata.filename, 'w+').close()
    except IOError as e:
        raise ServiceError(
            "Error creating file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def end_upload(metadata):
    try:
        stats = sftp.stat(metadata.filename)
        metadata.revision = stats.st_mtime
        metadata.write_revision()
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error while updating metadata on file '{}': {}".format(
                metadata.filename, e)
        )

    if metadata.filename in events_to_ignore:
        events_to_ignore.remove(metadata.filename)


@plug.handler()
def upload_chunk(metadata, offset, data):

    try:
        f = sftp.open(metadata.filename, 'a')
        f.seek(offset)
        f.write(data)
        f.close()
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error writting file '{}': {}".format(metadata.filename, e)
        )


def update_file(metadata, stat_res):

    try:
        metadata.size = stat_res.st_size
        metadata.revision = stat_res.st_mtime
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error updating file '{}': {}".format(metadata.filename, e)
        )
    else:
        plug.update_file(metadata)


@plug.handler()
def abort_upload(metadata):
    # Temporary solution to avoid problems
    try:
        sftp.remove(metadata.filename)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error deleting file '{}': {}".format(metadata.filename, e)
        )


class CheckChanges(threading.Thread):

    def __init__(self, timer, sftp):
        threading.Thread.__init__(self)
        self.stop = threading.Event()
        self.timer = timer
        self.sftp = sftp

    def check_folder(self, path=''):
        try:
            filelist = sftp.listdir(path)
        except IOError as e:
            raise ServiceError(
                "Error listing file in '{}': {}".format(path, e)
            )

        for f in filelist:
            filepath = os.path.join(path, f)
            try:
                stat_res = sftp.stat(str(filepath))

            except IOError as e:
                plug.logger.warn("Cant find file `{}` : {}",
                                 filepath, e)
                return

            metadata = plug.get_metadata(filepath)
            revision = metadata.revision
            revision = float(revision) if revision else .0

            if stat_res.st_mtime > revision:
                if S_ISDIR(stat_res.st_mode):
                    self.check_folder(filepath)
                else:
                    update_file(metadata, stat_res)

    def run(self):
        while not self.stop.isSet():
            self.check_folder()
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    global root
    root = plug.options['root']

    hostname = plug.options['hostname']
    username = plug.options['username']
    password = plug.options['password']
    port = int(plug.options['port'])
    timer = int(plug.options['check_modif_timer'])
    private_key_passphrase = plug.options['private_key_passphrase']
    private_key_path = plug.options.get('private_key_path', '~/.ssh/id_rsa')
    private_key_file = os.path.expanduser(private_key_path)

    private_key = paramiko.RSAKey.from_private_key_file(
        private_key_file, password=private_key_passphrase)

    transport = paramiko.Transport((hostname, port))
    try:
        if password != '':
            transport.connect(username=username, password=password)
        else:
            transport.connect(username=username, pkey=private_key)
    except paramiko.AuthenticationException as e:
        plug.logger.error("SSH driver connection failed : {}", e)
        transport.close()
        return

    global sftp
    sftp = paramiko.SFTPClient.from_transport(transport)

    try:
        sftp.chdir(root)
    except IOError as e:
        plug.logger.error("{}: {}", root, e)

    check_changes = CheckChanges(timer, sftp)
    check_changes.start()

    plug.listen()

    check_changes.stop()
    sftp.close()
    transport.close()
