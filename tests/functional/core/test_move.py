import pytest

from tests.utils.loop import CounterLoop


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def test_move_from_rep1(module_launcher):
    module_launcher.create_file('default', 'to_move1')
    module_launcher.move_file('default', 'to_move1', 'moved1',
                              *module_launcher.get_services('rep1', 'rep2'))


def test_move_from_rep2(module_launcher):
    module_launcher.create_file('default', 'to_move2')
    module_launcher.move_file('default', 'to_move2', 'moved2',
                              *module_launcher.get_services('rep2', 'rep1'))


def test_move_in_subdirs(module_launcher):
    src, dest = module_launcher.get_services('rep1', 'rep2')

    module_launcher.create_file('default', 'test/with/subdirs/foo')

    loop = CounterLoop(2)
    module_launcher.on_file_moved(
        loop.check, driver=src,
        src='test/with/subdirs/foo', dest='test/to/other/dir/bar',
        folder='default'
    )
    module_launcher.on_move_completed(
        loop.check, driver=dest,
        src='test/with/subdirs/foo', dest='test/to/other/dir/bar'
    )

    src.rename(
        src.path('default', 'test/with/subdirs/foo'),
        src.path('default', 'test/to/other/dir/bar')

    )
    loop.run(timeout=5)

    assert not dest.exists(dest.path('default', 'test/with/subdirs/foo'))
    assert dest.exists(dest.path('default', 'test/to/other/dir/bar'))


def test_move_dir_from_rep1(module_launcher):
    src, dest = module_launcher.get_services('rep1', 'rep2')

    module_launcher.create_file('default', 'dir/foo')
    module_launcher.create_file('default', 'dir/bar')

    loop = CounterLoop(4)
    module_launcher.on_file_moved(
        loop.check, driver=src, src='dir/foo', dest='other/foo',
        folder='default'
    )
    module_launcher.on_file_moved(
        loop.check, driver=src, src='dir/bar', dest='other/bar',
        folder='default'
    )
    module_launcher.on_move_completed(
        loop.check, driver=dest, src='dir/foo', dest='other/foo'
    )
    module_launcher.on_move_completed(
        loop.check, driver=dest, src='dir/bar', dest='other/bar'
    )

    src.rename(src.path('default', 'dir'), src.path('default', 'other'))

    loop.run(timeout=5)

    assert not dest.exists(dest.path('default', 'dir/foo'))
    assert not dest.exists(dest.path('default', 'dir/bar'))
    assert dest.exists(dest.path('default', 'other/foo'))
    assert dest.exists(dest.path('default', 'other/bar'))
