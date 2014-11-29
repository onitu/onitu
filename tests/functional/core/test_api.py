# -*- coding: utf-8 -*-

import requests
import time

from sys import version_info
if version_info.major == 2:
    from urllib import quote as quote
elif version_info.major == 3:
    from urllib.parse import quote as quote
import pytest

from tests.utils.loop import BooleanLoop
from tests.utils.testdriver import TestDriver
from tests.utils.units import KB

from onitu.utils import get_fid, b

rep1, rep2 = None, None


def get_services():
    global rep1, rep2
    rep1, rep2 = TestDriver(u'R€p1'), TestDriver(u'®èp2')
    return rep1, rep2


api_addr = "http://localhost:3862"
monitoring_path = u"/api/v1.0/services/{}/{}"
files_path = "/api/v1.0/files/{}/metadata"
services_path = "/api/v1.0/services"

STOP = ("stopped", "stopping")


@pytest.fixture(autouse=True)
def _(module_launcher, module_launcher_launch):
    pass


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


def is_running(circus_client, name):
    query = {
        'command': "status",
        'properties': {
            'name': name
        }
    }
    status = circus_client.call(query)
    return status['status'] == "active"


def start(circus_client, name):
    query = {
        'command': "start",
        'properties': {
            'name': name,
            'waiting': True
        }
    }
    circus_client.call(query)


def stop(circus_client, name):
    query = {
        'command': "stop",
        'properties': {
            'name': name,
            'waiting': True
        }
    }
    circus_client.call(query)


def create_file(module_launcher, filename, size):
    module_launcher.unset_all_events()
    loop = BooleanLoop()
    module_launcher.on_transfer_ended(
        loop.stop, d_from=rep1, d_to=rep2, filename=filename
    )
    rep1.generate(filename, size)
    loop.run(timeout=10)


def test_services():
    url = "{}{}".format(api_addr, services_path)

    r = get(url)
    json = extract_json(r)
    assert "services" in json
    j = json['services']
    services = sorted(j, key=lambda x: x['name'])
    assert len(services) == 2
    for (service, rep) in zip(services, (rep1, rep2)):
        assert service['driver'] == rep.type
        assert service['name'] == rep.name
        assert service['options'] == rep.options


def test_service_fail():
    url = "{}{}/{}".format(api_addr, services_path, "fail-repo")

    r = get(url)
    json = extract_json(r)
    assert r.status_code == 404
    assert json['status'] == "error"
    assert json['reason'] == "service fail-repo not found"


def test_service():
    url = u"{}{}/{}".format(api_addr, services_path, rep1.name)

    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['driver'] == rep1.type
    assert json['name'] == rep1.name
    assert json['options'] == rep1.options


def test_file_id():
    filename = u"onitu,is*a project ?!_-ùñï©œð€.txt"
    folder = u't€st'
    fid_path = u"/api/v1.0/files/id/{}/{}".format(
        quote(b(folder)), quote(b(filename))
    )
    url = u"{}{}".format(api_addr, fid_path)

    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json[filename] == get_fid(folder, filename)


def test_list_files(module_launcher):
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
        create_file(module_launcher, file_name, file_size)
    r = get(url)
    json = extract_json(r)
    files = json['files']
    assert r.status_code == 200
    assert len(files) == files_number
    for i in range(files_number):
        origin_file_size = origin_files[files[i]['filename']]
        assert files[i]['size'] == origin_file_size


def test_file_fail(module_launcher):
    create_file(module_launcher, "test_file.txt", 10 * KB)

    file_path = files_path.format("non-valid-id")
    url = "{}{}".format(api_addr, file_path)
    r = get(url)
    json = extract_json(r)

    assert r.status_code == 404
    assert json['status'] == "error"
    assert json['reason'] == "file {} not found".format("non-valid-id")


def test_file(module_launcher):
    create_file(module_launcher, "test_file.txt", 10 * KB)
    fid = get_fid("default", "test_file.txt")

    file_path = files_path.format(fid)
    url = "{}{}".format(api_addr, file_path)
    r = get(url)
    json = extract_json(r)

    assert r.status_code == 200
    assert json['fid'] == fid
    assert json['filename'] == "test_file.txt"
    assert json['size'] == 10 * KB
    assert json['mimetype'] == "text/plain"


def test_stop(circus_client):
    start(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "stop")
    url = u"{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['status'] == "ok"
    assert json['name'] == rep1.name
    assert 'time' in json
    assert is_running(circus_client, rep1.name) is False
    start(circus_client, rep1.name)


def test_start(circus_client):
    stop(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "start")
    url = u"{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['status'] == "ok"
    assert json['name'] == rep1.name
    assert 'time' in json
    assert is_running(circus_client, rep1.name) is True
    start(circus_client, rep1.name)


def test_restart(circus_client):
    start(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "restart")
    url = u"{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['status'] == "ok"
    assert json['name'] == rep1.name
    assert 'time' in json
    assert is_running(circus_client, rep1.name) is True


def test_stop_already_stopped(circus_client):
    stop(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "stop")
    url = u"{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 409
    assert json['status'] == "error"
    assert json['reason'] == u"service {} is already stopped".format(
        rep1.name
    )
    assert is_running(circus_client, rep1.name) is False
    start(circus_client, rep1.name)


def test_start_already_started(circus_client):
    start(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "start")
    url = u"{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 409
    assert json['status'] == "error"
    assert json['reason'] == u"service {} is already running".format(
        rep1.name
    )
    assert is_running(circus_client, rep1.name) is True


def test_restart_stopped(circus_client):
    stop(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "restart")
    url = u"{}{}".format(api_addr, monitoring)
    r = put(url)
    json = extract_json(r)
    assert r.status_code == 409
    assert json['status'] == "error"
    assert json['reason'] == u"service {} is stopped".format(
        rep1.name
    )
    assert is_running(circus_client, rep1.name) is False
    start(circus_client, rep1.name)


def test_stats_running(circus_client):
    start(circus_client, rep1.name)
    infos = ['age', 'cpu', 'create_time', 'ctime', 'mem', 'mem_info1',
             'mem_info2', 'started']
    monitoring = monitoring_path.format(rep1.name, "stats")
    url = u"{}{}".format(api_addr, monitoring)
    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['status'] == "ok"
    assert json['name'] == rep1.name
    assert 'time' in json
    keys = json['info'].keys()
    for info in infos:
        assert info in keys


def test_stats_stopped(circus_client):
    stop(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "stats")
    url = u"{}{}".format(api_addr, monitoring)
    r = get(url)
    json = extract_json(r)
    assert r.status_code == 409
    assert json['status'] == "error"
    assert json['reason'] == u"service {} is stopped".format(
        rep1.name
    )
    start(circus_client, rep1.name)


def test_status_started(circus_client):
    start(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "status")
    url = u"{}{}".format(api_addr, monitoring)
    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['name'] == rep1.name
    assert json['status'] == "active"


def test_status_stopped(circus_client):
    stop(circus_client, rep1.name)
    monitoring = monitoring_path.format(rep1.name, "status")
    url = u"{}{}".format(api_addr, monitoring)
    r = get(url)
    json = extract_json(r)
    assert r.status_code == 200
    assert json['name'] == rep1.name
    assert json['status'] in STOP
    start(circus_client, rep1.name)
