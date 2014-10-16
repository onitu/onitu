import requests
import time

from sys import version_info
if version_info.major == 2:
    from urllib import quote as quote
elif version_info.major == 3:
    from urllib.parse import quote as quote
from circus.client import CircusClient

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import BooleanLoop
from tests.utils.files import KB

from onitu.utils import get_fid, get_circusctl_endpoint

api_addr = "http://localhost:3862"
monitoring_path = "/api/v1.0/entries/{}/{}"
files_path = "/api/v1.0/files/{}/metadata"
entries_path = "/api/v1.0/entries"

circus_client = None
launcher, setup = None, None
rep1, rep2 = LocalStorageDriver("rep1"), TargetDriver("rep2")

STOP = ("stopped", "stopping")


def get(*args, **kwargs):
    while True:
        try:
            return requests.get(*args, **kwargs)
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)


def put(*args, **kwargs):
    while True:
        try:
            return requests.put(*args, **kwargs)
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)


def extract_json(req):
    try:
        return req.json()
    except Exception as e:
        print(req.status_code)
        print(req.content)
        raise e


def is_running(name):
    query = {
        'command': "status",
        'properties': {
            'name': name
        }
    }
    status = circus_client.call(query)
    return status['status'] == "active"


def start(name):
    query = {
        'command': "start",
        'properties': {
            'name': name,
            'waiting': True
        }
    }
    circus_client.call(query)


def stop(name):
    query = {
        'command': "stop",
        'properties': {
            'name': name,
            'waiting': True
        }
    }
    circus_client.call(query)


def create_file(filename, size):
    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    rep1.generate(filename, size)
    loop.run(timeout=10)


def setup_module(module):
    global launcher, setup, circus_client
    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path("/").sync(rep1.name, rep2.name))

    circus_client = CircusClient(endpoint=get_circusctl_endpoint(setup.name))

    launcher = Launcher(setup)
    launcher()


def teardown_module(module):
    launcher.close()


def test_entries():
    url = "{}{}".format(api_addr, entries_path)

    r = get(url)
    json = extract_json(r)
    assert "entries" in json
    j = json['entries']
    entries = sorted(j, key=lambda x: x['name'])
    assert len(entries) == 2
    for i in range(len(entries)):
        assert entries[i]['driver'] == "local_storage"
        assert entries[i]['name'] == "rep{}".format(i + 1)
        assert "root" in entries[i]['options']


def test_entry_fail():
    url = "{}{}/{}".format(api_addr, entries_path, "fail-repo")

    r = get(url)
    json = extract_json(r)
    assert r.status_code == 404
    assert json['status'] == "error"
    assert json['reason'] == "entry fail-repo not found"


def test_entry():
    url = "{}{}/{}".format(api_addr, entries_path, "rep1")

    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['driver'] == "local_storage"
    assert json['name'] == "rep1"
    assert "root" in json['options']


def test_file_id():
    filename = "onitu,is*a project ?!_-.txt"
    fid_path = "/api/v1.0/files/id/{}".format(quote(filename))
    url = "{}{}".format(api_addr, fid_path)

    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json[filename] == get_fid(filename)


def test_list_files():
    list_files = "/api/v1.0/files"
    url = "{}{}".format(api_addr, list_files)

    files_number = 10
    files_types = ['txt', 'pdf', 'exe', 'jpeg', 'png',
                   'mp4', 'zip', 'tar', 'rar', 'html']
    files_names = ["test_list_files-{}.{}".format(i, files_types[i])
                   for i in range(files_number)]
    origin_files = {files_names[i]: i * KB
                    for i in range(files_number)}

    for i in range(files_number):
        file_name = files_names[i]
        file_size = origin_files[file_name]
        create_file(file_name, file_size)
    r = get(url)
    json = extract_json(r)
    files = json['files']
    assert r.status_code == 200
    assert len(files) == files_number
    for i in range(files_number):
        origin_file_size = origin_files[files[i]['filename']]
        assert files[i]['size'] == origin_file_size


def test_file_fail():
    create_file("test_file.txt", 10 * KB)

    file_path = files_path.format("non-valid-id")
    url = "{}{}".format(api_addr, file_path)
    r = get(url)
    json = extract_json(r)

    assert r.status_code == 404
    assert json['status'] == "error"
    assert json['reason'] == "file {} not found".format("non-valid-id")


def test_file():
    create_file("test_file.txt", 10 * KB)
    fid = get_fid("test_file.txt")

    file_path = files_path.format(fid)
    url = "{}{}".format(api_addr, file_path)
    r = get(url)
    json = extract_json(r)

    assert r.status_code == 200
    assert json['fid'] == fid
    assert json['filename'] == "test_file.txt"
    assert json['size'] == 10 * KB
    assert json['mimetype'] == "text/plain"


def test_stop():
    start(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "stop")
    url = "{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['status'] == "ok"
    assert json['name'] == rep1.name
    assert 'time' in json
    assert is_running(rep1.name) is False
    start(rep1.name)


def test_start():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "start")
    url = "{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['status'] == "ok"
    assert json['name'] == rep1.name
    assert 'time' in json
    assert is_running(rep1.name) is True
    start(rep1.name)


def test_restart():
    start(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "restart")
    url = "{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['status'] == "ok"
    assert json['name'] == rep1.name
    assert 'time' in json
    assert is_running(rep1.name) is True


def test_stop_already_stopped():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "stop")
    url = "{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 409
    assert json['status'] == "error"
    assert json['reason'] == "entry {} is already stopped".format(
        rep1.name
    )
    assert is_running(rep1.name) is False
    start(rep1.name)


def test_start_already_started():
    start(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "start")
    url = "{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 409
    assert json['status'] == "error"
    assert json['reason'] == "entry {} is already running".format(
        rep1.name
    )
    assert is_running(rep1.name) is True


def test_restart_stopped():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "restart")
    url = "{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 409
    assert json['status'] == "error"
    assert json['reason'] == "entry {} is stopped".format(
        rep1.name
    )
    assert is_running(rep1.name) is False
    start(rep1.name)


def test_stats_running():
    start(rep1.name)
    infos = ['age', 'cpu', 'create_time', 'ctime', 'mem', 'mem_info1',
             'mem_info2', 'started']
    monitoring = monitoring_path.format(rep1.name, "stats")
    url = "{}{}".format(api_addr, monitoring)
    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['status'] == "ok"
    assert json['name'] == rep1.name
    assert 'time' in json
    keys = json['info'].keys()
    for info in infos:
        assert info in keys


def test_stats_stopped():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "stats")
    url = "{}{}".format(api_addr, monitoring)
    r = get(url)
    json = extract_json(r)
    assert r.status_code == 409
    assert json['status'] == "error"
    assert json['reason'] == "entry {} is stopped".format(
        rep1.name
    )
    start(rep1.name)


def test_status_started():
    start(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "status")
    url = "{}{}".format(api_addr, monitoring)
    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['name'] == rep1.name
    assert json['status'] == "active"


def test_status_stopped():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, "status")
    url = "{}{}".format(api_addr, monitoring)
    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['name'] == rep1.name
    assert json['status'] in STOP
    start(rep1.name)
