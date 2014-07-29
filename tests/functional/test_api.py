from requests import get, put

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import CounterLoop

api_addr = 'http://localhost:3862'
monitoring_path = '/api/v1.0/entries/{}/{}'
launcher, setup = None, None
rep1, rep2 = LocalStorageDriver('rep1'), TargetDriver('rep2')
json_file = 'test_startup.json'


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


def teardown_module(module):
    launcher.kill()
    setup.clean()


def start_driver(name):
    start = monitoring_path.format(name, 'start')
    start_url = '{}{}'.format(api_addr, start)
    put(start_url)


def stop_driver(name):
    stop = monitoring_path.format(name, 'stop')
    stop_url = '{}{}'.format(api_addr, stop)
    put(stop_url)


def test_stop():
    pass


def test_start():
    pass


def test_stop_already_stopped():
    pass


def test_start_already_started():
    pass


def test_restart_stopped():
    pass


def test_restart():
    pass


def test_stats_running():
    infos = ["age", "cpu", "create_time", "ctime", "mem", "mem_info1",
             "mem_info2", "started"]
    monitoring = monitoring_path.format(rep1.name, 'stats')
    url = '{}{}'.format(api_addr, monitoring)
    r = get(url)
    json = r.json()
    assert json['name'] == rep1.name.upper()
    assert json['status'] == 'ok'
    assert "time" in json
    keys = json['info'].keys()
    for info in infos:
        assert info in keys


def test_stats_stopped():
    monitoring = monitoring_path.format(rep1.name, 'stats')
    url = '{}{}'.format(api_addr, monitoring)
    stop_driver(rep1.name)
    r = get(url)
    json = r.json()
    assert json['status'] == 'error'
    assert json['reason'] == 'entry {} is stopped'.format(
        rep1.name.upper()
    )
    start_driver(rep1.name)


def test_status_started():
    monitoring = monitoring_path.format(rep1.name, 'status')
    url = '{}{}'.format(api_addr, monitoring)
    r = get(url)
    json = r.json()
    assert json['name'] == rep1.name.upper()
    assert json['status'] == 'active'


def test_status_stopped():
    monitoring = monitoring_path.format(rep1.name, 'status')
    url = '{}{}'.format(api_addr, monitoring)
    stop_driver(rep1.name)
    r = get(url)
    json = r.json()
    assert json['name'] == rep1.name.upper()
    assert json['status'] == 'stopped'
    start_driver(rep1.name)
