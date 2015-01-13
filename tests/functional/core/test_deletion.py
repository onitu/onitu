import pytest

from tests.utils.loop import CounterLoop


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def test_deletion_from_rep1(module_launcher):
    rep1, rep2 = module_launcher.get_services('rep1', 'rep2')
    module_launcher.create_file('default', 'del1')
    module_launcher.delete_file('default', 'del1', rep1, rep2)


def test_deletion_from_rep2(module_launcher):
    rep1, rep2 = module_launcher.get_services('rep1', 'rep2')
    module_launcher.create_file('default', 'del2')
    module_launcher.delete_file('default', 'del2', rep2, rep1)


def test_delete_dir(module_launcher):
    src, dest = module_launcher.get_services('rep1', 'rep2')

    module_launcher.create_file('default', 'dir/foo')
    module_launcher.create_file('default', 'dir/bar')

    loop = CounterLoop(4)
    module_launcher.on_file_deleted(
        loop.check, driver=src, filename='dir/foo', folder='default'
    )
    module_launcher.on_file_deleted(
        loop.check, driver=src, filename='dir/bar', folder='default'
    )
    module_launcher.on_deletion_completed(
        loop.check, driver=dest, filename='dir/foo'
    )
    module_launcher.on_deletion_completed(
        loop.check, driver=dest, filename='dir/bar'
    )

    src.rmdir(src.path('default', 'dir'))
    loop.run(timeout=5)

    assert not dest.exists(dest.path('default', 'dir/foo'))
    assert not dest.exists(dest.path('default', 'dir/bar'))
