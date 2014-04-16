import json

from bottle import Bottle, run, request, abort

from ..utils import connect_to_redis
from ..api.metadata import Metadata

host = 'localhost'
port = 3862

app = Bottle()

redis = connect_to_redis()
session = redis.session

def metadatas(fid):
    raw = session.hgetall('files:{}'.format(fid))
    if not raw:
        return None
    m = {'fid': fid}
    for name, (deserialize, _) in Metadata.PROPERTIES.items():
        m[name] = deserialize(raw.get(name))
    return m

@app.route('/api/v1.0/files', method='GET')
def get_files():
    files = [metadatas(fid) for fid in session.hgetall('files').values()]
    return json.dumps({'files': files})

@app.route('/api/v1.0/files/<fid:int>/metadata', method='GET')
def get_files(fid):
    m = metadatas(fid)
    if not m:
        abort(404)
    return json.dumps(m)

if __name__ == '__main__':
    run(app, host=host, port=port)
