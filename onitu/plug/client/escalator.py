from onitu.utils import pack_msg, unpack_msg


class KeyNotFound(Exception):
    pass


def escalator_request_method(name):
    def method(self, *args, **kwargs):
        resp = self.plug.request(pack_msg('escalator', name, args, kwargs))
        status, resp = unpack_msg(resp)
        if status != 1:
            raise KeyNotFound(*resp)
        return resp
    return method


class WriteBatch(object):
    def __init__(self, plug, transaction):
        self.plug = plug
        self.transaction = transaction
        self.requests = []

    def write(self):
        resp = self.plug.request(pack_msg('escalator', 'batch', [],
                                          {'transaction': self.transaction,
                                           'requests': self.requests}))
        unpack_msg(resp)
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if not self.transaction or not type:
            self.write()

    def put(self, *args, **kwargs):
        self.requests.append(('put', args, kwargs))

    def delete(self, *args, **kwargs):
        self.requests.append(('delete', args, kwargs))


class Escalator(object):
    def __init__(self, plug):
        super(Escalator, self).__init__()
        self.plug = plug

    clone = escalator_request_method('clone')
    get = escalator_request_method('get')
    exists = escalator_request_method('exists')
    put = escalator_request_method('put')
    delete = escalator_request_method('delete')
    range = escalator_request_method('range')

    def write_batch(self, transaction=False):
        return WriteBatch(self.plug, transaction)
