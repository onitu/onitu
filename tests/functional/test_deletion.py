from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import BooleanLoop, CounterLoop

launcher, setup = None, None
rep1, rep2 = LocalStorageDriver('rep1'), TargetDriver('rep2')


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


def test_deletion_from_rep1():
    copy_file('to_delete', 100)
    loop = CounterLoop(2)
    launcher.on_file_deleted(
        loop.check, driver='rep1', filename='to_delete'
    )
    launcher.on_deletion_completed(
        loop.check, driver='rep2', filename='to_delete'
    )
    rep1.unlink('to_delete')
    loop.run(timeout=5)
    assert not rep2.exists('to_delete')


def test_deletion_from_rep2():
    copy_file('to_delete', 100)
    loop = CounterLoop(2)
    launcher.on_file_deleted(
        loop.check, driver='rep2', filename='to_delete'
    )
    launcher.on_deletion_completed(
        loop.check, driver='rep1', filename='to_delete'
    )
    rep2.unlink('to_delete')
    loop.run(timeout=5)
    assert not rep1.exists('to_delete')


def test_delete_dir():
    rep1.mkdir('dir')
    copy_file('dir/foo', 100)
    copy_file('dir/bar', 100)
    loop = CounterLoop(4)
    launcher.on_file_deleted(
        loop.check, driver='rep1', filename='dir/foo'
    )
    launcher.on_file_deleted(
        loop.check, driver='rep1', filename='dir/bar'
    )
    launcher.on_deletion_completed(
        loop.check, driver='rep2', filename='dir/foo'
    )
    launcher.on_deletion_completed(
        loop.check, driver='rep2', filename='dir/bar'
    )
    rep1.rmdir('dir')
    loop.run(timeout=5)
    assert not rep2.exists('dir/foo')
    assert not rep2.exists('dir/bar')
