_registered_commands = {}


def command(name, value):
    if value in _registered_commands:
        raise ValueError('Command {} already exists'.format(value))
    _registered_commands[value] = name
    return value


def get_command(value):
    return _registered_commands[value]


CREATE = command('CREATE', b'\x01')
CONNECT = command('CONNECT', b'\x02')
GET = command('GET', b'\x03')
EXISTS = command('EXISTS', b'\x04')
PUT = command('PUT', b'\x05')
DELETE = command('DELETE', b'\x06')
RANGE = command('RANGE', b'\x07')
BATCH = command('BATCH', b'\x08')
