from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import TestingDriver, TargetDriver
from tests.utils.loop import BooleanLoop, CounterLoop

launcher, setup = None, None
rep1, rep2 = TestingDriver('rep1'), TargetDriver('rep2')


def setup_module(module):
    global launcher, setup
    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))
    launcher = Launcher(setup)
    launcher()


def teardown_module(module):
    launcher.close()


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
    copy_file('to_move1', 100)
    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver='rep1', src='to_move1', dest='moved1'
    )
    launcher.on_move_completed(
        loop.check, driver='rep2', src='to_move1', dest='moved1'
    )
    rep1.rename('to_move1', 'moved1')
    loop.run(timeout=5)
    assert not rep2.exists('to_move1')
    assert rep2.exists('moved1')


def test_move_from_rep2():
    copy_file('to_move2', 100)
    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver='rep2', src='to_move2', dest='moved2'
    )
    launcher.on_move_completed(
        loop.check, driver='rep1', src='to_move2', dest='moved2'
    )
    rep2.rename('to_move2', 'moved2')
    loop.run(timeout=5)
    assert not rep1.exists('to_move2')
    assert rep1.exists('moved2')


def test_move_in_subdirs():
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


def test_move_dir_from_rep1():
    rep1.mkdir('dir')
    copy_file('dir/foo', 100)
    copy_file('dir/bar', 100)
    loop = CounterLoop(4)
    launcher.on_file_moved(
        loop.check, driver='rep1', src='dir/foo', dest='other/foo'
    )
    launcher.on_file_moved(
        loop.check, driver='rep1', src='dir/bar', dest='other/bar'
    )
    launcher.on_move_completed(
        loop.check, driver='rep2', src='dir/foo', dest='other/foo'
    )
    launcher.on_move_completed(
        loop.check, driver='rep2', src='dir/bar', dest='other/bar'
    )
    rep1.rename('dir', 'other')
    loop.run(timeout=5)
    assert not rep2.exists('dir/foo')
    assert not rep2.exists('dir/bar')
    assert rep2.exists('other/foo')
    assert rep2.exists('other/bar')
