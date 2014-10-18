import os
import hashlib
import paramiko

from tests.utils.testdriver import TestDriver


class Driver(TestDriver):
    SPEED_BUMP = 1

    def __init__(self, *args, **options):

        # Clean the root
        root = options['root']
        if root.endswith('/'):
            root = root[:-1]

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
                    print "SFTP driver connection failed : {}".format(
                        private_key_error
                        )
                    transport.close()
                    return
                transport.connect(username=username, pkey=private_key)
        except paramiko.AuthenticationException as e:
            print "SFTP driver connection failed : {}".format(e)
            transport.close()
            return

        sftp = paramiko.SFTPClient.from_transport(transport)

        try:
            sftp.chdir(root)
        except IOError as e:
            print "{}: {}".format(root, e)

        super(Driver, self).__init__('sftp',
                                     *args,
                                     **options)

    def prefix_root(self, filename):
        root = str(self.root)
        if not filename.startswith(root):
            filename = root + filename
        return filename

    """@property
    def root(self):
        root = self.options['root']
        if not root.endswith('/'):
            root += '/'
        return path(root)
    """

    def close(self):
        self.sftp.rmdir(str(self.root))

    def mkdir(self, subdirs):
        self.sftp.mkdir(subdirs)

    def rmdir(self, path):
        self.sftp.rmdir(path)

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
