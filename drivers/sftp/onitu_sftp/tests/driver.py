import os
import uuid
import hashlib
import getpass
from stat import S_ISDIR

from onitu.plug import DriverError
from onitu.utils import u
from tests.utils import driver
from onitu_sftp.sftp import get_SFTP_client, create_file_subdirs


class Driver(driver.Driver):

    def __init__(self, *args, **options):
        default_user = getpass.getuser()
        # Default root
        self._root = os.getenv("ONITU_SFTP_ROOT",
                               u"/home/{}".format(default_user))
        if not self._root.endswith(u"/"):
            self._root += u"/"
        self._root += u(str(uuid.uuid4()))
        # To use the default configuration, you need:
        # An ssh server on your local machine
        # An ssh key pair without passphrase
        # This ssh key in your authorized_keys files
        # Otherwise, you can set your personal informations with the
        # env variables (e.g: ONITU_SFTP_HOSTNAME, ONITU_SFTP_USERNAME)
        options['hostname'] = os.getenv("ONITU_SFTP_HOSTNAME", u"localhost")
        options['username'] = os.getenv("ONITU_SFTP_USERNAME", default_user)
        options['password'] = os.getenv("ONITU_SFTP_PASSWORD", u"")
        options['port'] = os.getenv("ONITU_SFTP_PORT", 22)
        options['private_key_passphrase'] = os.getenv(
            "ONITU_SFTP_KEY_PASSPHRASE", u""
        )
        options['private_key_path'] = os.getenv(
            "ONITU_SFTP_KEY_PATH", u"~/.ssh/id_rsa"
        )
        options['changes_timer'] = os.getenv("ONITU_SFTP_CHANGES_TIMER", 5)

        super(Driver, self).__init__('sftp', *args, **options)

        self.sftp = get_SFTP_client(options['hostname'], options['port'],
                                    options['username'], options['password'],
                                    options['private_key_path'],
                                    options['private_key_passphrase'])

        if not self._root.endswith(u"/"):
            self._root += u"/"
        # Create the test directory
        create_file_subdirs(self.sftp, self._root)
        self.sftp.chdir(self._root)

    @property
    def root(self):
        return self._root

    def close(self):
        try:
            self.rmdir(self.root)
            self.sftp.close()
        except IOError as e:
            raise DriverError(e)

    def recursive_rmdir(self, path):
        """sftp.rmdir won't delete any non-empty folder so we got to go
        recursively removing each subdirectory and files before
        actually rmdir"""
        files = self.sftp.listdir_attr(path)
        if not path.endswith(u'/'):
            path += u"/"
        for f in files:
            fileName = u"{}{}".format(path, f.filename)
            if S_ISDIR(f.st_mode):
                self.recursive_rmdir(fileName)
            else:
                self.sftp.remove(fileName)
        self.sftp.rmdir(path)

    def mkdir(self, subdirs):
        if not subdirs.endswith(u"/"):
            subdirs += u"/"
        create_file_subdirs(self.sftp, subdirs)

    def rmdir(self, path):
        self.recursive_rmdir(path)

    def write(self, filename, content):
        create_file_subdirs(self.sftp, filename)
        f = self.sftp.open(filename, 'w+')
        f.write(content)
        f.close()

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def exists(self, filename):
        try:
            self.sftp.stat(filename)
        except IOError:
            return False
        return True

    def unlink(self, filename):
        self.sftp.remove(filename)

    def rename(self, source, target):
        self.sftp.rename(source, target)

    def checksum(self, filename):
        f = self.sftp.open(filename, 'r')
        data = f.read()
        md5 = hashlib.md5(data).hexdigest()
        f.close()
        return md5


class DriverFeatures(driver.DriverFeatures):
    move_file_to_onitu = False
