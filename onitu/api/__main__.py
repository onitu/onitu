import json

from bottle import Bottle, run, response, abort

from ..utils import connect_to_redis
from ..plug.metadata import Metadata

host = 'localhost'
port = 3862

app = Bottle()

redis = connect_to_redis()
session = redis.session


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
    raw = session.hgetall('files:{}'.format(fid))
    if not raw:
        return None
    m = {'fid': fid}
    for name, (deserialize, _) in Metadata.PROPERTIES.items():
        m[name] = deserialize(raw.get(name))
    return m


def entry(name):
    driver = session.get('drivers:{}:driver'.format(name))
    if not driver:
        return None
    options = session.hgetall('drivers:{}:options'.format(name))
    return {'name': name, 'driver': driver, 'options': options}


@app.route('/api/v1.0/files', method='GET')
def get_files():
    files = [metadatas(fid) for fid in session.hgetall('files').values()]
    return json.dumps({'files': files})


@app.route('/api/v1.0/files/<fid:int>/metadata', method='GET')
def get_file(fid):
    f = metadatas(fid)
    if not f:
        abort(404)
    return json.dumps(f)


@app.route('/api/v1.0/entries', method='GET')
def get_entries():
    entries = [entry(name) for name in session.smembers('entries')]
    return json.dumps({'entries': entries})


@app.route('/api/v1.0/entries/<name>', method='GET')
def get_entry(name):
    e = entry(name)
    if not e:
        abort(404)
    return json.dumps(e)


if __name__ == '__main__':
    run(app, host=host, port=port)
