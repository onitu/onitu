import pytest

from tests.utils.setup import Rule
from tests.utils.testdriver import TestDriver
from tests.utils.loop import CounterLoop, BooleanLoop


def init_setup(setup):
    setup.add(TestDriver('rep1', speed_bump=True))
    setup.add(TestDriver('rep2', speed_bump=True))
    setup.add_rule(Rule().match_path('/').sync('rep1', 'rep2'))


@pytest.fixture(autouse=True)
def _(auto_setup):
    pass


def crash(launcher, filename, src, dest):
    try:
        start_loop = BooleanLoop()
        end_loop = CounterLoop(2)
        launcher.on_transfer_started(
            start_loop.stop,
            d_from=src, d_to=dest,
            filename=filename
        )
        launcher.on_transfer_restarted(
            end_loop.check,
            d_from=src, d_to=dest,
            filename=filename
        )
        launcher.on_transfer_ended(
            end_loop.check,
            d_from=src, d_to=dest,
            filename=filename
        )

        src.generate(filename, 100)
        launcher()
        start_loop.run(timeout=10)
        launcher.kill()

        launcher()
        end_loop.run(timeout=10)

        assert src.checksum(filename) == dest.checksum(filename)
    finally:
        try:
            src.unlink(filename)
            dest.unlink(filename)
        except:
            pass
        launcher.close()
        pass


def test_crash_rep1_to_rep2(launcher):
    crash(launcher, 'crash_1', launcher.entries['rep1'],
          launcher.entries['rep2'])


def test_crash_rep2_to_rep1(launcher):
    crash(launcher, 'crash_2', launcher.entries['rep2'],
          launcher.entries['rep1'])
