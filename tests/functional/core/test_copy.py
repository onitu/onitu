import pytest

from tests.utils.units import KB, MB


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def test_small_copy(module_launcher):
    module_launcher.create_file('default', 'simple', 10)


def test_regular_copy(module_launcher):
    module_launcher.create_file('default', 'other', 100)


def test_same_copy(module_launcher):
    module_launcher.create_file('default', 'same', 100)
    module_launcher.create_file('default', 'same', 100)


def test_smaller_copy(module_launcher):
    module_launcher.create_file('default', 'smaller', 10 * KB)
    module_launcher.create_file('default', 'smaller', 1 * KB)


def test_bigger_copy(module_launcher):
    module_launcher.create_file('default', 'bigger', 1 * KB)
    module_launcher.create_file('default', 'bigger', 10 * KB)


def test_big_copy(module_launcher):
    module_launcher.create_file('default', 'big', 10 * MB)


def test_empty_file(module_launcher):
    module_launcher.create_file('default', 'empty', 0)


def test_subdirectories(module_launcher):
    module_launcher.create_file('default', 'sub/dir/deep/file', 100)
