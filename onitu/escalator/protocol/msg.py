from onitu.utils import pack_msg, unpack_msg
from . import status as protocol_status


def format_request(cmd, uid, *args):
    return pack_msg(cmd, uid, args)


def format_response(*args, **kwargs):
    status = kwargs.get('status', protocol_status.OK)
    return pack_msg(status.code, args)


def extract_request(msg):
    cmd, uid, args = unpack_msg(msg)
    return cmd, uid, args


def extract_response(msg):
    status_code, args = unpack_msg(msg)
    status = protocol_status.Status.get(status_code)
    if status.exception is not None:
        raise status.exception(*args)
    return args
