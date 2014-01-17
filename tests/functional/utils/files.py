import sh
import hashlib

MAX_SIZE_BS = 1024 * 1024


def generate(filename, bs, count=1):
    return sh.dd('if=/dev/urandom', 'of={}'.format(filename),
                 'bs={}'.format(bs), 'count={}'.format(count))


def checksum(filename):
    h = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()
