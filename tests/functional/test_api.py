from time import sleep
from circus.client import CircusClient
from requests import get, put

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import CounterLoop

api_addr = 'http://localhost:3862'
monitoring_path = '/api/v1.0/entries/{}/{}'
circus_client = CircusClient()
launcher, setup = None, None
rep1, rep2 = LocalStorageDriver('rep1'), TargetDriver('rep2')
json_file = 'test_startup.json'


def is_running(name):
    query = {
        "command": "status",
        "properties": {
            "name": name
        }
    }
    status = circus_client.call(query)
    return status['status'] == 'active'


def start(name):
    query = {
        "command": "start",
        "properties": {
            "name": name,
            "waiting": True
        }
    }
    circus_client.call(query)


def stop(name):
    query = {
        "command": "stop",
        "properties": {
            "name": name,
            "waiting": True
        }
    }
    circus_client.call(query)


def setup_module(module):
    global launcher, setup
    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))
    setup.save(json_file)
    loop = CounterLoop(4)
    launcher = Launcher(json_file)
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher.on_api_started(loop.check)
    launcher()
    try:
        loop.run(timeout=5)
    except:
        teardown_module(module)
        raise
    # TODO: remove the sleep
    sleep(5.)


def teardown_module(module):
    launcher.kill()
    setup.clean()


def test_stop():
    start(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'stop')
    url = '{}{}'.format(api_addr, monitoring)
    r = put(url)
    json = r.json()
    assert json['status'] == 'ok'
    assert json['name'] == rep1.name.upper()
    assert "time" in json
    assert is_running(rep1.name) is False
    start(rep1.name)


def test_start():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'start')
    url = '{}{}'.format(api_addr, monitoring)
    r = put(url)
    json = r.json()
    assert json['status'] == 'ok'
    assert json['name'] == rep1.name.upper()
    assert "time" in json
    assert is_running(rep1.name) is True
    start(rep1.name)


def test_restart():
    start(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'restart')
    url = '{}{}'.format(api_addr, monitoring)
    r = put(url)
    json = r.json()
    assert json['status'] == 'ok'
    assert json['name'] == rep1.name.upper()
    assert "time" in json
    assert is_running(rep1.name) is True


def test_stop_already_stopped():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'stop')
    url = '{}{}'.format(api_addr, monitoring)
    r = put(url)
    json = r.json()
    assert json['status'] == 'error'
    assert json['reason'] == 'entry {} is already stopped'.format(
        rep1.name.upper()
    )
    assert is_running(rep1.name) is False
    start(rep1.name)


def test_start_already_started():
    start(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'start')
    url = '{}{}'.format(api_addr, monitoring)
    r = put(url)
    json = r.json()
    assert json['status'] == 'error'
    assert json['reason'] == 'entry {} is already running'.format(
        rep1.name.upper()
    )
    assert is_running(rep1.name) is True


def test_restart_stopped():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'restart')
    url = '{}{}'.format(api_addr, monitoring)
    r = put(url)
    json = r.json()
    assert json['status'] == 'error'
    assert json['reason'] == 'entry {} is stopped'.format(
        rep1.name.upper()
    )
    assert is_running(rep1.name) is False
    start(rep1.name)


def test_stats_running():
    start(rep1.name)
    infos = ["age", "cpu", "create_time", "ctime", "mem", "mem_info1",
             "mem_info2", "started"]
    monitoring = monitoring_path.format(rep1.name, 'stats')
    url = '{}{}'.format(api_addr, monitoring)
    r = get(url)
    json = r.json()
    assert json['status'] == 'ok'
    assert json['name'] == rep1.name.upper()
    assert "time" in json
    keys = json['info'].keys()
    for info in infos:
        assert info in keys


def test_stats_stopped():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'stats')
    url = '{}{}'.format(api_addr, monitoring)
    r = get(url)
    json = r.json()
    assert json['status'] == 'error'
    assert json['reason'] == 'entry {} is stopped'.format(
        rep1.name.upper()
    )
    start(rep1.name)


def test_status_started():
    start(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'status')
    url = '{}{}'.format(api_addr, monitoring)
    r = get(url)
    json = r.json()
    assert json['name'] == rep1.name.upper()
    assert json['status'] == 'active'


def test_status_stopped():
    stop(rep1.name)
    monitoring = monitoring_path.format(rep1.name, 'status')
    url = '{}{}'.format(api_addr, monitoring)
    r = get(url)
    json = r.json()
    assert json['name'] == rep1.name.upper()
    assert json['status'] == 'stopped'
    start(rep1.name)
