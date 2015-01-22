from . import cmd as protocol_cmd


class Status(type):
    _registered_status = []

    def __new__(cls, name, bases, dct):
        dct['code'] = len(cls._registered_status)
        c = super(Status, cls).__new__(cls, name, bases, dct)
        cls._registered_status.append(c)
        return c

    @classmethod
    def get(cls, code):
        return cls._registered_status[code]


def new_status(name, exception):
    return Status(name, (object,), {'exception': exception})


OK = new_status('OK', None)


class DatabaseNotFound(KeyError):
    def __init__(self, name):
        KeyError.__init__(self, 'No database {} found'.format(repr(name)))
DB_NOT_FOUND = new_status('DB_NOT_FOUND', DatabaseNotFound)


class DatabaseError(Exception):
    def __init__(self, name):
        Exception.__init__(self, 'Can not open database {}'.format(repr(name)))
DB_ERROR = new_status('DB_ERROR', DatabaseError)


class NoDatabaseSelected(ValueError):
    def __init__(self, uid):
        ValueError.__init__(self, 'No database is selected (received uid {})'.
                            format(uid))
NO_DB = new_status('NO_DB', NoDatabaseSelected)


class CommandNotFound(KeyError):
    def __init__(self, cmd):
        KeyError.__init__(self, 'No such command {}'.format(repr(cmd)))
CMD_NOT_FOUND = new_status('CMD_NOT_FOUND', CommandNotFound)


class InvalidArguments(TypeError):
    def __init__(self, cmd):
        TypeError.__init__(self, 'Invalid arguments for command {}'.
                           format(protocol_cmd.get_command(cmd)))
INVALID_ARGS = new_status('INVALID_ARGS', InvalidArguments)


class KeyNotFound(KeyError):
    def __init__(self, key):
        KeyError.__init__(self, 'Key {} not found in base'.format(repr(key)))
KEY_NOT_FOUND = new_status('KEY_NOT_FOUND', KeyNotFound)


class EscalatorClosed(RuntimeError):
    def __init__(self):
        RuntimeError.__init__(self, 'The client was closed')
ESCALATOR_CLOSED = new_status('ESCALATOR_CLOSED', EscalatorClosed)


class Error(Exception):
    def __init__(self):
        Exception.__init__(self, 'An error occurred')
ERROR = new_status('ERROR', Error)
