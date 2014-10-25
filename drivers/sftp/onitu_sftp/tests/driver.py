import os
import uuid
import hashlib
import paramiko
import getpass

from tests.utils.testdriver import TestDriver
from stat import S_ISDIR


class Driver(TestDriver):

    def __init__(self, *args, **options):

        # Clean the root
        username = getpass.getuser()
        self.default_root = "/home/{}/{}".format(username, str(uuid.uuid4()))

        self.root = os.getenv("ONITU_SFTP_ROOT", self.default_root)
        if self.root.endswith('/'):
            self.root = self.root[:-1]

        # To use this default configuration, you need:
            # An ssh server on your local machine
            # An ssh key pair without passphrase
            # This ssh key in your authorized_keys files
        # Otherwise, you can set your personal informations with your
        # environment variables (e.g: ONITU_SFTP_HOSTNAME, ONITU_SFTP_USERNAME)
        options['root'] = self.root
        options['hostname'] = os.getenv("ONITU_SFTP_HOSTNAME", "localhost")
        options['username'] = os.getenv("ONITU_SFTP_USERNAME", username)
        options['password'] = os.getenv("ONITU_SFTP_PASSWORD", "")
        options['port'] = os.getenv("ONITU_SFTP_PORT", 22)
        options['private_key_passphrase'] = os.getenv(
            "ONITU_SFTP_KEY_PASSPHRASE", ""
        )
        options['private_key_path'] = os.getenv(
            "ONITU_SFTP_KEY_PATH", "~/.ssh/id_rsa"
        )
        options['changes_timer'] = os.getenv("ONITU_SFTP_CHANGES_TIMER", 10)

        super(Driver, self).__init__('sftp', *args, **options)

        hostname = options['hostname']
        username = options['username']
        password = options['password']
        port = options['port']
        private_key_passphrase = options['private_key_passphrase']
        private_key_path = options['private_key_path']

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
                    raise RuntimeError(
                        "SFTP driver connection failed : {}".format(
                            private_key_error
                        )
                    )
                    transport.close()
                    return

                transport.connect(username=username, pkey=private_key)
        except paramiko.AuthenticationException as e:
            raise RuntimeError(
                "SFTP driver connection failed : {}".format(e)
            )
            transport.close()
            return

        self.sftp = paramiko.SFTPClient.from_transport(transport)
        self.create_dirs(self.root)

        try:
            self.sftp.chdir(self.root)
        except IOError as e:
            raise RuntimeError(
                "{}: {}".format(self.root, e)
            )

    def rm_folder(self, path):
        try:
            filelist = self.sftp.listdir(path)
        except IOError as e:
            raise RuntimeError(
                "Error listing file in '{}': {}".format(path, e)
            )

        for f in filelist:
            filepath = os.path.join(path, f)
            stat_res = self.sftp.stat(filepath)

            if S_ISDIR(stat_res.st_mode):
                self.rm_folder(filepath)
            else:
                self.sftp.remove(filepath)

        # Remove the root
        self.sftp.rmdir(path)

    def create_dirs(self, path):
        parent_exists = True

        tmp_path = ''
        if path.startswith('/'):
            tmp_path = '/'
        dirs = path.split('/')

        for d in dirs:
            tmp_path = os.path.join(tmp_path, d)
            if tmp_path == '':
                continue

            # If the parent exists, we check if the current path exists
            if parent_exists is True:
                try:
                    self.sftp.stat(tmp_path)
                # The current path doesn't exists, so we create it
                except IOError:
                    try:
                        parent_exists = False
                        self.sftp.mkdir(tmp_path)
                    except IOError as e:
                        raise RuntimeError(
                            "Error creating dir '{}': {}".format(tmp_path, e)
                            )

            # If the parent doesn't exist, we can create the current dir
            # without check if it exists
            else:
                try:
                    self.sftp.mkdir(tmp_path)
                except IOError as e:
                    raise RuntimeError(
                        "Error creating dir '{}': {}".format(tmp_path, e)
                    )

    def close(self):
        self.rmdir(self.root)

    def mkdir(self, subdirs):
        self.create_dirs(subdirs)

    def rmdir(self, path):
        self.rm_folder(path)

    def write(self, filename, content):
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
        return hashlib.md5(data).hexdigest()
