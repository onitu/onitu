import pytest

from tests.utils.driver import TestingDriver
from tests.utils.loop import CounterLoop

rep1, rep2 = TestingDriver("rep1"), TestingDriver("rep2")


@pytest.fixture(autouse=True)
def _(module_launcher_initialize):
    pass


def launch_with_files(launcher, prefix, n, size, delete=True):
    files = ['{}{}'.format(prefix, i) for i in range(n)]

    try:
        for filename in files:
            rep1.generate(filename, size)

        loop = CounterLoop(n)
        for filename in files:
            launcher.on_transfer_ended(
                loop.check, d_from='rep1', d_to='rep2', filename=filename
            )

        launcher()
        loop.run(timeout=(10 + n // 5))

        for filename in files:
            assert rep1.checksum(filename) == rep2.checksum(filename)
    finally:
        launcher.kill()

        if delete:
            for filename in files:
                try:
                    rep1.unlink(filename)
                    rep2.unlink(filename)
                except:
                    pass


def test_changes_one_file(module_launcher):
    launch_with_files(module_launcher, 'one', 1, 100)


def test_changes_few_files(module_launcher):
    launch_with_files(module_launcher, 'few', 10, 100)


def test_changes_many_files(module_launcher):
    launch_with_files(module_launcher, 'many', 100, 10)


def test_updating_files(module_launcher):
    launch_with_files(module_launcher, 'up', 10, 100, delete=False)
    launch_with_files(module_launcher, 'up', 10, 100)
