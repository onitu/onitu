from onitu.api.plug import Plug

plug = Plug()

@plug.handler
def send_chunk(chunk):
    # send ...
    return True

@plug.handler
def read_chunk(chunk):
    content = "Fill this with the real chunk, bitch !"
    return content

def start(*args, **kwargs):
    plug.start()
    plug.join()
