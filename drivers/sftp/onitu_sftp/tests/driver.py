import os
import hashlib
import paramiko

from tests.utils.testdriver import TestDriver


class Driver(TestDriver):

    def __init__(self, *args, **options):
        super(Driver, self).__init__('sftp', *args, **options)

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

        sftp = paramiko.SFTPClient.from_transport(transport)

        try:
            sftp.chdir(root)
        except IOError as e:
            raise RuntimeError(
                "{}: {}".format(root, e)
            )


    def create_dirs(self, path):
        parent_exists = True
        tmp_path = './'
        dirs = path.split('/')

        for d in dirs:
            tmp_path = os.path.join(tmp_path, d)

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

            # If the parent doesn't exist, we can create the current dir without
            # check if it exists
            else:
                try:
                    sftp.mkdir(tmp_path)
                except IOError as e:
                    raise RuntimeError(
                        "Error creating dir '{}': {}".format(tmp_path, e)
                    )


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
        self.sftp.rmdir('.')

    def mkdir(self, subdirs):
        create_dirs(subdirs)

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
