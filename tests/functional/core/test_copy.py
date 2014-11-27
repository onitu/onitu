import pytest

from tests.utils.loop import BooleanLoop
from tests.utils.units import KB, MB


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
    assert src.checksum(filename) == dest.checksum(filename)


def test_small_copy(module_launcher):
    copy_file(module_launcher, 'simple', 10)


def test_regular_copy(module_launcher):
    copy_file(module_launcher, 'other', 100)


def test_same_copy(module_launcher):
    copy_file(module_launcher, 'same', 100)
    copy_file(module_launcher, 'same', 100)


def test_smaller_copy(module_launcher):
    copy_file(module_launcher, 'smaller', 10 * KB)
    copy_file(module_launcher, 'smaller', 1 * KB)


def test_bigger_copy(module_launcher):
    copy_file(module_launcher, 'bigger', 1 * KB)
    copy_file(module_launcher, 'bigger', 10 * KB)


def test_big_copy(module_launcher):
    copy_file(module_launcher, 'big', 10 * MB)


def test_empty_file(module_launcher):
    copy_file(module_launcher, 'empty', 0)


def test_subdirectories(module_launcher):
    module_launcher.entries['rep1'].mkdir('sub/dir/deep/')
    copy_file(module_launcher, 'sub/dir/deep/file', 100)
