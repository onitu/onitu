import sys

from logbook import Logger
from logbook.queues import ZeroMQHandler
from bottle import Bottle, run, response, abort

from onitu.escalator.client import Escalator
from onitu.plug.metadata import Metadata

host = 'localhost'
port = 3862

app = Bottle()

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


if __name__ == '__main__':
    with ZeroMQHandler(sys.argv[1], multi=True).applicationbound():
        logger.info("Starting on {}:{}".format(host, port))
        run(app, host=host, port=port, quiet=True)
