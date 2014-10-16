import sys

from sys import version_info
if version_info.major == 2:
    from urllib import unquote as unquote
elif version_info.major == 3:
    from urllib.parse import unquote as unquote
from logbook import Logger
from logbook.queues import ZeroMQHandler
from bottle import Bottle, run, response, abort, redirect
from circus.client import CircusClient

from onitu.escalator.client import Escalator
from onitu.utils import get_fid, get_logs_uri, get_circusctl_endpoint

host = 'localhost'
port = 3862

app = Bottle()

session = sys.argv[1]
circus_client = CircusClient(endpoint=get_circusctl_endpoint(session))
escalator = Escalator(session)
logger = Logger("REST API")


@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = (
        'PUT, GET, POST, DELETE, OPTIONS'
    )
    response.headers['Access-Control-Allow-Headers'] = (
        'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'
    )


def entry(name):
    driver = escalator.get('entry:{}:driver'.format(name), default=None)
    if not driver:
        return None
    options = escalator.get('entry:{}:options'.format(name))
    return {'name': name, 'driver': driver, 'options': options}


def entry_exists(name):
    names = [entry for entry in escalator.get('entries')]
    return name in names


def entry_is_running(name):
    query = {
        "command": "status",
        "properties": {
            "name": name
        }
    }
    status = circus_client.call(query)
    if status['status'] == "active":
        return True
    else:
        return False


def error(error_code=500, error_message="internal server error"):
    response.status = error_code
    resp = {
        "status": "error",
        "reason": error_message
    }
    return resp


def file_not_found(name):
    return error(
        error_code=404,
        error_message="file {} not found".format(name)
    )


def entry_not_found(name):
    return error(
        error_code=404,
        error_message="entry {} not found".format(name)
    )


def entry_not_running(name, already=False):
    fmt = "entry {} is {}stopped".format
    # "already" in case a stop has been requested on an already stopped entry
    err_msg = fmt(name, "already ") if already else fmt(name, "")
    return error(
        error_code=409,
        error_message=err_msg
    )


def timeout():
    return error(
        error_code=408,
        error_message="timed out"
    )


@app.route('/api', method='GET')
@app.route('/api/v1.0', method='GET')
def api_doc():
    redirect("https://onitu.readthedocs.org/en/latest/api.html")


@app.route('/api/v1.0/files/id/<name>', method='GET')
def get_file_id(name):
    name = unquote(name)
    return {name: get_fid(name)}


@app.route('/api/v1.0/files', method='GET')
def get_files():
    files = [metadata for key, metadata in escalator.range('file:')
             if key.count(b':') == 1]
    for metadata in files:
        metadata['fid'] = get_fid(metadata['filename'])
    return {'files': files}


@app.route('/api/v1.0/files/<fid>/metadata', method='GET')
def get_file(fid):
    fid = unquote(fid)
    metadata = escalator.get('file:{}'.format(fid), default=None)
    if not metadata:
        return file_not_found(fid)
        abort(404)
    metadata['fid'] = fid
    return metadata


@app.route('/api/v1.0/entries', method='GET')
def get_entries():
    entries = [entry(name) for name in escalator.get('entries')]
    return {'entries': entries}


@app.route('/api/v1.0/entries/<name>', method='GET')
def get_entry(name):
    name = unquote(name)
    e = entry(name)
    if not e:
        return entry_not_found(name)
    # Do not check if entry is running as we must be able to get info anyway
    return e


@app.route('/api/v1.0/entries/<name>/stats', method='GET')
def get_entry_stats(name):
    name = unquote(name)
    try:
        if not entry(name):
            return entry_not_found(name)
        if not entry_is_running(name):
            return entry_not_running(name)
        query = {
            "command": "stats",
            "properties": {
                "name": name
            }
        }
        stats = circus_client.call(query)
        pid = next(iter(stats['info'].keys()))
        resp = {
            "info": {
                "age": stats['info'][pid]['age'],
                "cpu": stats['info'][pid]['cpu'],
                "create_time": stats['info'][pid]['create_time'],
                "ctime": stats['info'][pid]['ctime'],
                "mem": stats['info'][pid]['mem'],
                "mem_info1": stats['info'][pid]['mem_info1'],
                "mem_info2": stats['info'][pid]['mem_info2'],
                "started": stats['info'][pid]['started'],
            },
            "name": stats['name'],
            "status": stats['status'],
            "time": stats['time'],
        }
    except Exception as e:
        resp = error(error_message=str(e))
    return resp


@app.route('/api/v1.0/entries/<name>/status', method='GET')
def get_entry_status(name):
    name = unquote(name)
    try:
        if not entry(name):
            return entry_not_found(name)
        query = {
            "command": "status",
            "properties": {
                "name": name
            }
        }
        status = circus_client.call(query)
        resp = {
            "name": name,
            "status": status['status'],
            "time": status['time'],
        }
    except Exception as e:
        resp = error(error_message=str(e))
    return resp


@app.route('/api/v1.0/entries/<name>/start', method='PUT')
def start_entry(name):
    name = unquote(name)
    try:
        if not entry(name):
            return entry_not_found(name)
        if entry_is_running(name):
            return error(
                error_code=409,
                error_message="entry {} is already running".format(name)
            )
        query = {
            "command": "start",
            "properties": {
                "name": name,
                "waiting": True
            }
        }
        start = circus_client.call(query)
        resp = {
            "name": name,
            "status": start['status'],
            "time": start['time'],
        }
    except Exception as e:
        resp = error(error_message=str(e))
    return resp


@app.route('/api/v1.0/entries/<name>/stop', method='PUT')
def stop_entry(name):
    name = unquote(name)
    try:
        if not entry(name):
            return entry_not_found(name)
        if not entry_is_running(name):
            return entry_not_running(name, already=True)
        query = {
            "command": "stop",
            "properties": {
                "name": name,
                "waiting": True
            }
        }
        stop = circus_client.call(query)
        resp = {
            "name": name,
            "status": stop['status'],
            "time": stop['time'],
        }
    except Exception as e:
        resp = error(error_message=str(e))
    return resp


@app.route('/api/v1.0/entries/<name>/restart', method='PUT')
def restart_entry(name):
    name = unquote(name)
    try:
        if not entry_exists(name):
            return entry_not_found(name)
        if not entry_is_running(name):
            return entry_not_running(name)
        query = {
            "command": "restart",
            "properties": {
                "name": name,
                "waiting": True
            }
        }
        restart = circus_client.call(query)
        resp = {
            "name": name,
            "status": restart['status'],
            "time": restart['time'],
        }
    except Exception as e:
        resp = error(error_message=str(e))
    return resp


if __name__ == '__main__':
    with ZeroMQHandler(get_logs_uri(session), multi=True).applicationbound():
        logger.info("Starting on {}:{}".format(host, port))
        run(app, host=host, port=port, quiet=True)
