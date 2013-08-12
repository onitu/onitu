from onitu.api.plug import Plug
from os import path, makedirs

root = './'
plug = Plug()

@plug.handler
def send_chunk(chunk):
    # send ...
    return True

@plug.handler
def read_chunk(filename, offset, size):
    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.read(size)

@plug.handler
def write_chunk(filename, offset, chunk):
    with open(filename, 'rb') as f:
        f.seek(offset)
        return f.write(chunk)

@plug.handler
def new_file(metadatas):
    filepath = root + metadatas['path']
    if not path.exists(filepath):
        makedirs(filepath)
    open(path.join(filepath, metadatas['filename']), 'w+').close()

def start(*args, **kwargs):
    plug.start()
    plug.join()
