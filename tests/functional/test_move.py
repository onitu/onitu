from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import BooleanLoop, CounterLoop

launcher, setup = None, None
rep1, rep2 = LocalStorageDriver('rep1'), TargetDriver('rep2')
json_file = 'test_deletion.json'


def setup_module(module):
    global launcher, setup
    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))
    setup.save(json_file)
    loop = CounterLoop(3)
    launcher = Launcher(json_file)
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    try:
        loop.run(timeout=5)
    except:
        teardown_module(module)
        raise


def teardown_module(module):
    launcher.kill()
    setup.clean()


def copy_file(filename, size):
    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    rep1.generate(filename, size)
    loop.run(timeout=10)
    assert rep2.exists(filename)


def test_move_from_rep1():
    copy_file('to_move', 100)
    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver='rep1', src='to_move', dest='moved'
    )
    launcher.on_move_completed(
        loop.check, driver='rep2', src='to_move', dest='moved'
    )
    rep1.rename('to_move', 'moved')
    loop.run(timeout=5)
    assert not rep2.exists('to_move')
    assert rep2.exists('moved')


def test_move_from_rep2():
    copy_file('to_move', 100)
    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver='rep2', src='to_move', dest='moved'
    )
    launcher.on_move_completed(
        loop.check, driver='rep1', src='to_move', dest='moved'
    )
    rep2.rename('to_move', 'moved')
    loop.run(timeout=5)
    assert not rep1.exists('to_move')
    assert rep1.exists('moved')


def test_move_with_dirs():
    rep1.mkdir('test/with/subdirs/')
    copy_file('test/with/subdirs/foo', 100)
    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver='rep1',
        src='test/with/subdirs/foo', dest='test/to/other/dir/bar'
    )
    launcher.on_move_completed(
        loop.check, driver='rep2',
        src='test/with/subdirs/foo', dest='test/to/other/dir/bar'
    )
    rep1.mkdir('test/to/other/dir')
    rep1.rename('test/with/subdirs/foo', 'test/to/other/dir/bar')
    loop.run(timeout=5)
    assert not rep2.exists('test/with/subdirs/foo')
    assert rep2.exists('test/to/other/dir/bar')
