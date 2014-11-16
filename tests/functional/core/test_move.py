import pytest

from tests.utils.loop import BooleanLoop, CounterLoop


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def copy_file(launcher, filename, size):
    src, dest = launcher.get_entries('rep1', 'rep2')
    launcher.unset_all_events()
    loop = BooleanLoop()
    launcher.on_transfer_ended(
        loop.stop, d_from=src, d_to=dest, filename=filename
    )
    src.generate(filename, size)
    loop.run(timeout=10)
    assert dest.exists(filename)


def move_file(launcher, old_filename, new_filename, src, dest):
    copy_file(launcher, old_filename, 100)
    loop = CounterLoop(2)
    launcher.on_file_moved(
        loop.check, driver=src, src=old_filename, dest=new_filename
    )
    launcher.on_move_completed(
        loop.check, driver=dest, src=old_filename, dest=new_filename
    )
    src.rename(old_filename, new_filename)
    loop.run(timeout=5)
    assert not dest.exists(old_filename)
    assert dest.exists(new_filename)


def test_move_from_rep1(module_launcher):
    move_file(module_launcher, 'to_move1', 'moved1',
              *module_launcher.get_entries('rep1', 'rep2'))


def test_move_from_rep2(module_launcher):
    move_file(module_launcher, 'to_move1', 'moved1',
              *module_launcher.get_entries('rep2', 'rep1'))


def test_move_in_subdirs(module_launcher):
    src, dest = module_launcher.get_entries('rep1', 'rep2')
    src.mkdir('test/with/subdirs/')
    copy_file(module_launcher, 'test/with/subdirs/foo', 100)
    loop = CounterLoop(2)
    module_launcher.on_file_moved(
        loop.check, driver=src,
        src='test/with/subdirs/foo', dest='test/to/other/dir/bar'
    )
    module_launcher.on_move_completed(
        loop.check, driver=dest,
        src='test/with/subdirs/foo', dest='test/to/other/dir/bar'
    )
    src.mkdir('test/to/other/dir')
    src.rename('test/with/subdirs/foo', 'test/to/other/dir/bar')
    loop.run(timeout=5)
    assert not dest.exists('test/with/subdirs/foo')
    assert dest.exists('test/to/other/dir/bar')


def test_move_dir_from_rep1(module_launcher):
    src, dest = module_launcher.get_entries('rep1', 'rep2')
    src.mkdir('dir')
    copy_file(module_launcher, 'dir/foo', 100)
    copy_file(module_launcher, 'dir/bar', 100)
    loop = CounterLoop(4)
    module_launcher.on_file_moved(
        loop.check, driver=src, src='dir/foo', dest='other/foo'
    )
    module_launcher.on_file_moved(
        loop.check, driver=src, src='dir/bar', dest='other/bar'
    )
    module_launcher.on_move_completed(
        loop.check, driver=dest, src='dir/foo', dest='other/foo'
    )
    module_launcher.on_move_completed(
        loop.check, driver=dest, src='dir/bar', dest='other/bar'
    )
    src.rename('dir', 'other')
    loop.run(timeout=5)
    assert not dest.exists('dir/foo')
    assert not dest.exists('dir/bar')
    assert dest.exists('other/foo')
    assert dest.exists('other/bar')
