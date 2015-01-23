import os
import threading

import paramiko
from paramiko import PasswordRequiredException, SSHException

from stat import S_ISDIR
from onitu.plug import Plug, DriverError, ServiceError
from onitu.escalator.client import EscalatorClosed

plug = Plug()
events_to_ignore = set()
sftp = None


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
        error = (u"Private key file {} is encrypted, passphrase required ({})"
                 .format(pkey_path, pre))
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
    sftpClient = paramiko.SFTPClient.from_transport(transport)
    return sftpClient


def get_SFTP_client_from_plug():
    """Helper function to connect an SFTP client with the plug infos."""
    return get_SFTP_client(plug.options['hostname'],
                           plug.options['port'],
                           plug.options['username'],
                           plug.options['password'],
                           plug.options['private_key_path'],
                           plug.options['private_key_passphrase'])


def create_file_subdirs(sftpClient, filepath):
    # Getting rid of the filename
    lastSlash = filepath.rindex(u"/")
    finalPath = filepath[:lastSlash]
    dirs = finalPath.split(u"/")

    currentDir = u""
    doStat = True
    try:
        while dirs:
            currentDir += dirs.pop(0) + u"/"
            if doStat:
                try:
                    sftpClient.stat(currentDir)
                # The current dir doesn't exists, so we create it
                except IOError as ioe:
                    if ioe.errno == 2:
                        sftpClient.mkdir(currentDir)
                        # If a dir was not found, it means all the next
                        # won't exist either. So stop bothering to stat
                        doStat = False
                    else:
                        raise
            else:
                sftpClient.mkdir(currentDir)
    except IOError as ioe:
        raise ServiceError(u"Error while creating subdirs {}: {}"
                           .format(finalPath, ioe))


def update_metadata(metadata, mtime, update_file=False):
    metadata.extra['mtime'] = mtime
    metadata.write()
    if update_file:
        plug.update_file(metadata)


@plug.handler()
def close():
    plug.logger.debug("Closing")
    if sftp is not None:
        sftp.close()


@plug.handler()
def get_file(metadata):
    plug.logger.debug(u"Getting remote file {}", metadata.path)
    try:
        f = sftp.open(metadata.path, 'r')
        # "If reading the entire file, pre-fetching can dramatically improve
        # the download speed by avoiding roundtrip latency."
        # http://docs.paramiko.org/en/latest/api/sftp.html
        # #paramiko.sftp_file.SFTPFile.prefetch
        f.prefetch()
        data = f.read()
        return data
    except IOError as e:
        raise ServiceError("Error getting file '{}': {}"
                           .format(metadata.path, e))


@plug.handler()
def start_upload(metadata):
    plug.logger.debug(u"Starting upload of {}", metadata.path)
    try:
        create_file_subdirs(sftp, metadata.path)
        plug.logger.debug(u"Adding {} to ignored files", metadata.path)
        events_to_ignore.add(metadata.path)
    except IOError as ioe:
        raise ServiceError(u"Failed to start upload of {}: {}"
                           .format(metadata.path, ioe))


@plug.handler()
def upload_file(metadata, content):
    plug.logger.debug(u"Uploading file {}", metadata.path)
    try:
        f = sftp.open(metadata.path, 'w+')
        f.write(content)
        f.close()
    except (IOError, OSError) as e:
        raise ServiceError("Error writing file '{}': {}"
                           .format(metadata.path, e))
    plug.logger.debug(u"Uploading file {} - Done", metadata.path)


@plug.handler()
def end_upload(metadata):
    plug.logger.debug(u"Ending upload of file {}", metadata.path)
    try:
        stat_res = sftp.stat(metadata.path)
        update_metadata(metadata, stat_res.st_mtime,
                        update_file=False)
    except (IOError, OSError) as e:
        raise ServiceError(u"Error during upload ending on file '{}': {}"
                           .format(metadata.path, e))
    finally:
        if metadata.path in events_to_ignore:
            plug.logger.debug(u"Removing {} of ignored files", metadata.path)
            events_to_ignore.remove(metadata.path)


@plug.handler()
def abort_upload(metadata):
    plug.logger.debug(u"Aborting upload of file {}", metadata.path)
    delete_file(metadata)


@plug.handler()
def delete_file(metadata):
    plug.logger.debug(u"Deleting file {}", metadata.path)
    try:
        sftp.remove(metadata.path)
    except (IOError, OSError) as e:
        raise ServiceError(u"Error deleting file '{}': {}"
                           .format(metadata.path, e))
    finally:
        if metadata.path in events_to_ignore:
            plug.logger.debug(u"Removing {} of ignored files", metadata.path)
            events_to_ignore.remove(metadata.path)


@plug.handler()
def move_file(old_metadata, new_metadata):
    plug.logger.debug(u"Moving file {} to {}",
                      old_metadata.path, new_metadata.path)
    try:
        create_file_subdirs(sftp, new_metadata.path)
        sftp.rename(old_metadata.path, new_metadata.path)
    except IOError as ioe:
        raise ServiceError(u"Error while moving file {} to {}: {}"
                           .format(old_metadata.path, new_metadata.path, ioe))


class CheckChanges(threading.Thread):

    def __init__(self, folder, sftpClient, timer):
        super(CheckChanges, self).__init__()
        self.stopEvent = threading.Event()
        self.folder = folder
        self.sftp = sftpClient
        self.timer = timer
        self.deletedFiles = {}  # useful for deletion detection
        dirPath = folder.path
        if not dirPath.endswith(u"/"):
            dirPath += u"/"
        # Get in the right folder
        try:
            create_file_subdirs(self.sftp, dirPath)
            plug.logger.debug(u"Changing directory to {}", dirPath)
            self.sftp.chdir(dirPath)
        except IOError as e:
            raise ServiceError(u"Unable to chdir into {}: {}"
                               .format(dirPath, e))

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
        plug.logger.debug(u"Checking regular file {}", filePath)
        metadata = plug.get_metadata(filePath, self.folder)
        onitu_mtime = metadata.extra.get('mtime', 0)
        if regFile.st_mtime > onitu_mtime:
            plug.logger.debug(u"Updating {}", filePath)
            metadata.size = regFile.st_size
            if metadata.path not in events_to_ignore:
                update_metadata(metadata, regFile.st_mtime,
                                update_file=True)
            else:
                plug.logger.debug(u"File {} is in transfer - skipped",
                                  metadata.path)
        else:
            plug.logger.debug(u"File {} is up-to-date", filePath)
        # Cross this file out from the deleted files list
        if filePath in self.deletedFiles:
            del self.deletedFiles[filePath]

    def delete_removed_files(self):
        """After having checked remote files, files still sitting in the
        self.deletedFiles haven't been found, so we delete them on Onitu
        side."""
        for filePath in self.deletedFiles.keys():
            if filePath not in events_to_ignore:
                metadata = plug.get_metadata(filePath, self.folder)
                plug.delete_file(metadata)

    def run(self):
        while not self.stopEvent.isSet():
            try:
                plug.logger.debug(u"Checking remote folder {}",
                                  self.folder.path)
                # Get a list of the files we know. Check them out as we find
                # them. The remaining are files that were deleted when we
                # weren't looking.
                self.deletedFiles = plug.list(self.folder)
                self.check_directory(".")
                self.delete_removed_files()
            except EscalatorClosed:
                # We are closing
                self.stop()
                return
            except IOError as ioe:
                plug.logger.error(u"An error occurred while checking remote "
                                  u"folder {}: {}", self.folder.path, ioe)
            plug.logger.debug("Next check in {} seconds", self.timer)
            self.stopEvent.wait(self.timer)

    def stop(self):
        plug.logger.debug("Closing SFTP connection")
        self.sftp.close()
        self.stopEvent.set()


def start():
    if (plug.options.get('password', None) is None
       and plug.options.get('private_key_path', None) is None):
        raise DriverError("You must configure a password or a private key")

    global sftp
    sftp = get_SFTP_client_from_plug()

    timer = plug.options['changes_timer']
    for folder in plug.folders_to_watch:
        # Get a different client for each folder.
        sftpClient = get_SFTP_client_from_plug()
        # Launch the changes detection
        check_changes = CheckChanges(folder, sftpClient, timer)
        check_changes.daemon = True
        check_changes.start()

    plug.listen()
