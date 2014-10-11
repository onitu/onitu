from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import CounterLoop

launcher, setup = None, None
rep1, rep2 = LocalStorageDriver("rep1"), TargetDriver("rep2")


def setup_module(module):
    global setup, launcher
    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))
    launcher = Launcher(setup)


def teardown_module(module):
    launcher.close()


def launch_with_files(prefix, n, size, delete=True):
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


def test_changes_one_file():
    launch_with_files('one', 1, 100)


def test_changes_few_files():
    launch_with_files('few', 10, 100)


def test_changes_many_files():
    launch_with_files('many', 100, 10)


def test_updating_files():
    launch_with_files('up', 10, 100, delete=False)
    launch_with_files('up', 10, 100)
