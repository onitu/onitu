import os
import hashlib

KB = 1 << 10
MB = 1 << 20
GB = 1 << 30


def generate(filename, size):
    with open(filename, 'wb+') as f:
        f.write(os.urandom(size))


def checksum(filename):
    h = hashlib.md5()
    with open(filename, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()
