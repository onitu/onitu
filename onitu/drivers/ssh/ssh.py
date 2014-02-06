import os

import threading
import paramiko

from stat import S_ISDIR
from onitu.api import Plug

plug = Plug()
root = None
sftp = None
terminated = False
events_to_ignore = set()


def create_dirs(sftp, path):
    dirs = path.split('/')
    base = sftp.getcwd()

    for d in dirs:
        try:
            sftp.chdir(d)
        except IOError:
            sftp.mkdir(d, 0777)
            sftp.chdir(d)

    sftp.chdir(base)


@plug.handler()
def get_chunk(filepath, offset, size):
    f = sftp.open(str(filepath), 'r')
    data = f.readv([(offset, size)])

    for d in data:
        return d


@plug.handler()
def start_upload(metadata):
    #create_dirs(sftp, str(os.path.dirname(metadata.filename)))
    events_to_ignore.add(metadata.filename)
    sftp.open(metadata.filename, 'w+').close()


@plug.handler()
def end_upload(metadata):
    stats = sftp.stat(metadata.filename)

    metadata.revision = stats.st_mtime
    metadata.write_revision()

    if metadata.filename in events_to_ignore:
        events_to_ignore.remove(metadata.filename)


@plug.handler()
def upload_chunk(filename, offset, data):
    events_to_ignore.add(filename)

    f = sftp.open(filename, 'a')
    f.seek(offset)
    f.write(data)
    f.flush()
    f.close()


def update_file(metadata, stat_res):
    if metadata.filename in events_to_ignore:
        return

    metadata.size = stat_res.st_size
    metadata.revision = stat_res.st_mtime
    plug.update_file(metadata)


class CheckChanges(threading.Thread):

    def __init__(self, timer, sftp):
        threading.Thread.__init__(self)
        self.stop = threading.Event()
        self.timer = timer
        self.sftp = sftp

    def check_folder(self, path=''):
        filelist = sftp.listdir(path)

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


def start(*args, **kwargs):
    plug.start(*args, **kwargs)

    global root
    root = plug.options['root']

    hostname = plug.options['hostname']
    username = plug.options['username']
    password = plug.options['password']
    pkey_passphrase = plug.options['pkey_passphrase']
    port = int(plug.options['port'])
    timer = int(plug.options['changes_timer'])
    pkey_path = plug.options.get('pkey_path', '~/.ssh/id_rsa')
    pkey_file = os.path.expanduser(pkey_path)

    my_pkey = paramiko.RSAKey.from_private_key_file(pkey_file,
                                                    password=pkey_passphrase)

    transport = paramiko.Transport((hostname, port))
    try:
        if password != '':
            transport.connect(username=username, password=password)
        else:
            transport.connect(username=username, pkey=my_pkey)
    except paramiko.AuthenticationException as e:
        plug.logger.error("SSH driver connection failed : {}", e)
        transport.close()
        return

    global sftp
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    try:
        sftp.chdir(root)
    except IOError as e:
        plug.logger.error("CHDIR failed : {}", e)

    check_changes = CheckChanges(timer, sftp)
    check_changes.start()

    plug.listen()

    check_changes.stop()
    sftp.close()
    transport.close()
