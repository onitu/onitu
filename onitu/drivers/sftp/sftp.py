import os
import threading

import paramiko

from stat import S_ISDIR
from onitu.plug import Plug, ServiceError

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
def get_file(metadata):
    full_path = get_full_path(metadata.filename)

    try:
        stats = sftp.stat(full_path)
        f = sftp.open(full_path, 'r')
        data = f.readv([(0, stats.st_size)])

        for d in data:
            return d

    except (IOError) as e:
        raise ServiceError(
            "Error getting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def start_upload(metadata):
    full_path = get_full_path(metadata.filename)

    events_to_ignore.add(full_path)
    create_dirs(sftp, str(os.path.dirname(metadata.filename)))

    try:
        sftp.open(full_path, 'w+').close()
    except IOError as e:
        raise ServiceError(
            "Error creating file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def end_upload(metadata):
    full_path = get_full_path(metadata.filename)

    try:
        stat_res = sftp.stat(full_path)
        metadata.size = stat_res.st_size
        metadata.extra['revision'] = stat_res.st_mtime
        metadata.write()

    except (IOError, OSError) as e:
        raise ServiceError(
            "Error while updating metadata on file '{}': {}".format(
                metadata.filename, e)
        )

    if metadata.filename in events_to_ignore:
        events_to_ignore.remove(full_path)


@plug.handler()
def upload_file(metadata, content):
    full_path = get_full_path(metadata.filename)

    try:
        f = sftp.open(full_path, 'w')
        f.write(content)
        f.close()
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error writting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def abort_upload(metadata):
    full_path = get_full_path(metadata.filename)

    # Temporary solution to avoid problems
    try:
        sftp.remove(full_path)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error deleting file '{}': {}".format(metadata.filename, e)
        )


def update_file(metadata, stat_res):

    try:
        metadata.size = stat_res.st_size
        metadata.extra['revision'] = stat_res.st_mtime
        metadata.write()
        plug.update_file(metadata)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error updating file '{}': {}".format(metadata.filename, e)
        )


def get_full_path(filename):
    global root
    return root + '/' + filename


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
            onitu_rev = metadata.extra.get('revision', 0.)

            if stat_res.st_mtime > onitu_rev:
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
    global plug
    global root

    # Clean the root
    root = plug.options['root']
    if root.endswith('/'):
        root = root[:-1]

    hostname = plug.options['hostname']
    username = plug.options['username']
    password = plug.options['password']
    port = int(plug.options['port'])
    timer = int(plug.options['changes_timer'])
    private_key_passphrase = plug.options['private_key_passphrase']
    private_key_path = plug.options.get('private_key_path', '~/.ssh/id_rsa')
    private_key_file = os.path.expanduser(private_key_path)

    private_key_error = None
    try:
        private_key = paramiko.RSAKey.from_private_key_file(
            private_key_file, password=private_key_passphrase)
    except IOError as e:
        private_key_error = e

    transport = paramiko.Transport((hostname, port))
    try:
        if password != '':
            transport.connect(username=username, password=password)
        else:
            if private_key_error is not None:
                plug.logger.error("SFTP driver connection failed : {}",
                                  private_key_error)
                transport.close()
                return
            transport.connect(username=username, pkey=private_key)
    except paramiko.AuthenticationException as e:
        plug.logger.error("SFTP driver connection failed : {}", e)
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
