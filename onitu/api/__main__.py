import sys

from logbook import Logger
from logbook.queues import ZeroMQHandler
from bottle import Bottle, run, response, abort
from circus.client import CircusClient

from onitu.escalator.client import Escalator
from onitu.plug.metadata import Metadata

host = 'localhost'
port = 3862

app = Bottle()

circus_client = CircusClient(endpoint=sys.argv[4])
escalator = Escalator(sys.argv[2], sys.argv[3])
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


def metadatas(fid):
    raw = escalator.get('file:{}'.format(fid), default=None)
    if not raw:
        return None
    m = {'fid': fid}
    for name, (deserialize, _) in Metadata.PROPERTIES.items():
        m[name] = deserialize(raw.get(name))
    return m


def entry(name):
    driver = escalator.get('entry:{}:driver'.format(name))
    if not driver:
        return None
    options = escalator.get('entry:{}:options'.format(name))
    return {'name': name, 'driver': driver, 'options': options}


def entry_exists(name):
    names = [entry.upper() for entry in escalator.get('entries')]
    return name in names


def entry_is_running(name):
    names = [entry.upper() for entry in escalator.get('entries')]
    if name.upper() not in names:
        return False
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


def entry_not_found(name):
    return error(
        error_code=404,
        error_message="entry {} not found".format(name)
    )


def entry_not_running(name):
    return error(
        error_code=409,
        error_message="entry {} is stopped".format(name)
    )


def timeout():
    return error(
        error_code=408,
        error_message="timed out"
    )


@app.route('/api/v1.0/files', method='GET')
def get_files():
    files = [metadatas(fid) for fid in escalator.get('files')]
    return {'files': files}


@app.route('/api/v1.0/files/<fid:int>/metadata', method='GET')
def get_file(fid):
    f = metadatas(fid)
    if not f:
        abort(404)
    return f


@app.route('/api/v1.0/entries', method='GET')
def get_entries():
    entries = [entry(name) for name in escalator.get('entries')]
    return {'entries': entries}


@app.route('/api/v1.0/entries/<name>', method='GET')
def get_entry(name):
    e = entry(name)
    if not e:
        abort(404)
    return e


@app.route('/api/v1.0/entries/<name>/stats', method='GET')
def get_entry_stats(name):
    name = name.upper()
    try:
        if not entry_exists(name):
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
        pid = list(stats['info'].keys())[0]
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
        return resp
    except Exception as e:
        resp = error(error_message=str(e))
        return resp


@app.route('/api/v1.0/entries/<name>/status', method='GET')
def get_entry_status(name):
    name = name.upper()
    try:
        if not entry_exists(name):
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
        return resp
    except Exception as e:
        resp = error(error_message=str(e))
        return resp


@app.route('/api/v1.0/entries/<name>/start', method='PUT')
def start_entry(name):
    name = name.upper()
    try:
        if not entry_exists(name):
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
        return resp
    except Exception as e:
        resp = error(error_message=str(e))
        return resp


@app.route('/api/v1.0/entries/<name>/stop', method='PUT')
def stop_entry(name):
    name = name.upper()
    try:
        if not entry_exists(name):
            return entry_not_found(name)
        if not entry_is_running(name):
            return error(
                error_code=409,
                error_message="entry {} is already stopped".format(name)
            )
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
        return resp
    except Exception as e:
        resp = error(error_message=str(e))
        return resp


@app.route('/api/v1.0/entries/<name>/restart', method='PUT')
def restart_entry(name):
    name = name.upper()
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
        return resp
    except Exception as e:
        resp = error(error_message=str(e))
        return resp


if __name__ == '__main__':
    with ZeroMQHandler(sys.argv[1], multi=True).applicationbound():
        logger.info("Starting on {}:{}".format(host, port))
        run(app, host=host, port=port, quiet=True)
