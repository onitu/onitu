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


def get_SFTP_client(hostname, port, username, password,
                    pkey_path, passphrase):
    """Helper function to connect with SFTP. Tries to connect with the given
    connection infos and, if successful, returns a SFTPClient ready to be
    used.
    Raises DriverError if an error occurred during the client setup."""
    transport = paramiko.Transport((hostname, port))
    try:
        if password != '':
            transport.connect(username=username, password=password)
        else:
            pkey_path = os.path.expanduser(pkey_path)
            privateKey = get_private_key(pkey_path, passphrase)
            transport.connect(username=username, pkey=privateKey)
    except SSHException as se:
        raise DriverError(u"Failed to connect to host: {}".format(se))
    sftp = paramiko.SFTPClient.from_transport(transport)
    return sftp


def get_SFTP_client_from_plug():
    """Helper function to connect an SFTP client with the plug infos."""
    return get_SFTP_client(plug.options['hostname'],
                           plug.options['port'],
                           plug.options['username'],
                           plug.options['password'],
                           plug.options['private_key_path'],
                           plug.options['private_key_passphrase'])


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

#
# @plug.handler()
# def close():
#     sftp.close()
#     transport.close()


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

    def __init__(self, folder, sftp, timer):
        super(CheckChanges, self).__init__()
        self.stopEvent = threading.Event()
        self.folder = folder
        self.sftp = sftp
        self.timer = timer
        # Get in the right folder
        try:
            plug.logger.debug(u"Changing directory to {}".format(folder.path))
            self.sftp.chdir(folder.path)
        except IOError as e:
            raise ServiceError(u"Unable to chdir into {}: {}"
                               .format(folder.path, e))

    def check_directory(self, path):
        """Recursively searches for all regular files under a directory and
        all its subdirectories, and update them if they have changed."""
        plug.logger.debug(u"Checking remote subdirectory {}".format(path))
        files = self.sftp.listdir_attr(path)
        folders = []
        for f in files:
            if S_ISDIR(f.st_mode):
                folders.append(f)
            else:
                self.check_regular_file(path, f)
        for folder in folders:
            dirPath = folder.filename
            if path != ".":
                dirPath = "{}/{}".format(path, dirPath)
            self.check_directory(dirPath)

    def check_regular_file(self, path, regFile):
        """Compares the modification time Onitu has for this file and its
        actual modification time. If the latter is more recent, triggers an
        update."""
        filePath = regFile.filename
        if path != ".":
            filePath = "{}/{}".format(path, filePath)
        plug.logger.debug(u"Checking regular file {}".format(filePath))
        metadata = plug.get_metadata(filePath, self.folder)
        onitu_mtime = metadata.extra.get('mtime', 0)
        if regFile.st_mtime > onitu_mtime:
            plug.logger.debug(u"Updating {}".format(filePath))
            # metadata.size = regFile.attr['st_size']
            # metadata.extra['mtime'] = regFile.attr['st_mtime']
            # plug.update_file(metadata)
        else:
            plug.logger.debug(u"File {} is up-to-date".format(filePath))

    def run(self):
        while not self.stopEvent.isSet():
            try:
                plug.logger.debug(u"Checking remote folder {}"
                                  .format(self.folder.path))
                self.check_directory(".")
            except EscalatorClosed:
                # We are closing
                self.stop()
                return
            except IOError as ioe:
                plug.logger.error(u"An error occurred while checking remote "
                                  u"folder {}: {}"
                                  .format(self.folder.path, ioe))
            self.stopEvent.wait(self.timer)

    def stop(self):
        plug.logger.debug("Closing SFTP connection")
        self.sftp.close()
        self.stopEvent.set()


def start():
    if (plug.options.get('password', None) is None
       and plug.options.get('private_key_path', None) is None):
        raise DriverError("You must configure a password or a private key")
    timer = plug.options['changes_timer']
    for folder in plug.folders_to_watch:
        # Get a different client for each folder.
        sftp = get_SFTP_client_from_plug()
        # Launch the changes detection
        check_changes = CheckChanges(folder, sftp, timer)
        check_changes.daemon = True
        check_changes.start()

    plug.listen()
