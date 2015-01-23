import os
import hashlib

from io import BytesIO

from tests.utils import driver
from onitu_webdav.wd import get_WEBDAV_client, create_dirs
from onitu.utils import get_random_string, b, dirname


class Driver(driver.Driver):
    def __init__(self, *args, **options):
        options['hostname'] = os.getenv(
            "ONITU_WEBDAV_HOSTNAME", "http://localhost"
        )
        options['username'] = os.getenv("ONITU_WEBDAV_USERNAME", "")
        options['password'] = os.getenv("ONITU_WEBDAV_PASSWORD", "")
        options['changes_timer'] = os.getenv("ONITU_WEBDAV_CHANGES_TIMER", 5)
        root = os.getenv("ONITU_WEBDAV_ROOT", u"/")

        self._root = root + get_random_string(10)

        hostname = options['hostname']
        username = options['username']
        password = options['password']

        super(Driver, self).__init__('webdav', *args, **options)

        self.webd = get_WEBDAV_client(hostname, username, password)

        create_dirs(self.webd, self._root)

    @property
    def root(self):
        return self._root

    def close(self):
        self.rmdir(self.root)

    def mkdir(self, subdirs):
        create_dirs(self.webd, subdirs)

    def rmdir(self, path):
        self.webd.clean(b(path))

    def write(self, filename, content):
        create_dirs(self.webd, dirname(filename))
        buff = BytesIO(content)
        self.webd.upload_from(buff, b(filename))

    def generate(self, filename, size):
        self.write(filename, os.urandom(size))

    def exists(self, filename):
        try:
            self.webd.info(b(filename))
        except:
            return False
        return True

    def unlink(self, filename):
        self.webd.clean(b(filename))

    def rename(self, source, target):
        self.webd.move(remote_path_from=b(source), remote_path_to=b(target))

    def checksum(self, filename):
        buff = BytesIO()
        self.webd.download_to(buff, b(filename))
        data = buff.getvalue()
        md5 = hashlib.md5(data).hexdigest()
        return md5


class DriverFeatures(driver.DriverFeatures):
    move_file_to_onitu = False
