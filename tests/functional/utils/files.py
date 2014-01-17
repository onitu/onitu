import sh
import hashlib


def generate(filename, size):
    return sh.dd('if=/dev/urandom', 'of={}'.format(filename),
                 'bs={}'.format(size), 'count=1')


def checksum(filename):
    h = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()
