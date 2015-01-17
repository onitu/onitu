import os
import threading

import paramiko
from paramiko import PasswordRequiredException, SSHException

from stat import S_ISDIR
from onitu.plug import Plug, DriverError, ServiceError
from onitu.escalator.client import EscalatorClosed

plug = Plug()
events_to_ignore = set()


def get_private_key(pkey_path, passphrase):
    """Returns a Paramiko.RSAKey based upon the given informations.
    Raises DriverError if anything has gone wrong generating the key."""
    error = None
    private_key = None
    try:
        private_key = paramiko.RSAKey.from_private_key_file(
            pkey_path, password=passphrase)
    except IOError as e:
        error = u"Unable to read file {}: {}".format(pkey_path, e)
    except PasswordRequiredException as pre:
        error = (u"Private key file {} is encrypted, passphrase required,"
                 u" has {} ({})".format(pkey_path, passphrase, pre))
    except SSHException as se:
        error = u"Private key file {} is invalid ({})".format(pkey_path, se)
    finally:
        if error is not None:
            raise DriverError(u"Failed to create private key: {}"
                              .format(error))
    return private_key


def get_SFTP_client(hostname, port, username, password, privateKey):
    """Helper function to connect with SFTP. Tries to connect with the given
    connection infos and, if successful, returns a SFTPClient ready to be
    used.
    Raises DriverError if an error occurred during the client setup."""
    transport = paramiko.Transport((hostname, port))
    try:
        if password != '':
            transport.connect(username=username, password=password)
        else:
            transport.connect(username=username, pkey=privateKey)
    except SSHException as se:
        raise DriverError(u"Failed to connect to host: {}".format(se))
    sftp = paramiko.SFTPClient.from_transport(transport)
    return sftp


def create_dirs(sftp, path):
    parent_exists = True
    tmp_path = './'
    dirs = path.split('/')

    for d in dirs:
        tmp_path = os.path.join(tmp_path, d)

        # If the parent exists, we check if the current path exists
        if parent_exists is True:
            try:
                sftp.stat(tmp_path)
            # The current path doesn't exists, so we create it
            except IOError:
                try:
                    parent_exists = False
                    sftp.mkdir(tmp_path)
                except IOError as e:
                    raise ServiceError(
                        "Error creating dir '{}': {}".format(tmp_path, e)
                        )
        # If the parent doesn't exist, we can create the current dir without
        # check if it exists
        else:
            try:
                sftp.mkdir(tmp_path)
            except IOError as e:
                raise ServiceError(
                    "Error creating dir '{}': {}".format(tmp_path, e)
                    )


@plug.handler()
def get_file(metadata):

    try:
        f = sftp.open(metadata.filename, 'r')
        data = f.read()
        return data

    except IOError as e:
        raise ServiceError(
            "Error getting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def start_upload(metadata):
    events_to_ignore.add(metadata.filename)
    create_dirs(sftp, os.path.dirname(metadata.filename))


@plug.handler()
def end_upload(metadata):
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

    # Temporary solution to avoid problems
    try:
        sftp.remove(metadata.filename)
    except (IOError, OSError) as e:
        raise ServiceError(
            "Error deleting file '{}': {}".format(metadata.filename, e)
        )


@plug.handler()
def close():
    sftp.close()
    transport.close()


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


class CheckChanges(threading.Thread):

    def __init__(self, timer, sftp):
        super(CheckChanges, self).__init__()
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
                stat_res = sftp.stat(filepath)

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
            try:
                self.check_folder()
            except EscalatorClosed:
                # We are closing
                return
            self.stop.wait(self.timer)

    def stop(self):
        self.stop.set()


def start():
    # First retrieve the user private key
    privateKeyPath = plug.options.get('private_key_path', '~/.ssh/id_rsa')
    privateKeyPath = os.path.expanduser(privateKeyPath)
    passphrase = plug.options['private_key_passphrase']
    privateKey = get_private_key(privateKeyPath, passphrase)

    for folder in plug.folders_to_watch:
        # Get a different client for each folder.
        sftp = get_SFTP_client(plug.options['hostname'],
                               plug.options['port'],
                               plug.options['username'],
                               plug.options['password'],
                               privateKey)
        try:
            sftp.chdir(folder.path)
        except IOError as e:
            plug.logger.error(u"Unable to chdir into {}: {}", folder.path, e)
        # Launch the changes detection
        check_changes = CheckChanges(plug.options['changes_timer'], sftp)
        check_changes.daemon = True
        check_changes.start()

    plug.listen()
