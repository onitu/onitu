import pytest

from tests.utils.loop import CounterLoop


@pytest.fixture(autouse=True)
def _(module_auto_setup):
    pass


def launch_with_files(launcher, prefix, n, size, delete=True):
    src, dest = launcher.get_services('rep1', 'rep2')
    files = ['{}{}'.format(prefix, i) for i in range(n)]

    try:
        for filename in files:
            src.generate(src.path('default', filename), size)

        loop = CounterLoop(n)
        for filename in files:
            launcher.on_transfer_ended(
                loop.check, d_from=src, d_to=dest, filename=filename
            )

        launcher()
        loop.run(timeout=(10 + n // 5))

        for filename in files:
            assert src.checksum(src.path('default', filename)) == \
                dest.checksum(dest.path('default', filename))
    finally:
        launcher.close()
        launcher.unset_all_events()

        if delete:
            for filename in files:
                try:
                    src.unlink(src.path('default', filename))
                    dest.unlink(dest.path('default', filename))
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
