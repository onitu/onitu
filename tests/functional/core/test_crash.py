import pytest

from tests.utils.testdriver import TestDriver
from tests.utils.loop import CounterLoop, BooleanLoop

rep1, rep2 = None, None


def get_services():
    global rep1, rep2
    rep1 = TestDriver('rep1', speed_bump=True)
    rep2 = TestDriver('rep2', speed_bump=True)
    return rep1, rep2


@pytest.fixture(autouse=True)
def _(auto_setup):
    pass


def crash(launcher, filename, src, dest):
    try:
        start_loop = BooleanLoop()
        end_loop = CounterLoop(2)
        launcher.on_transfer_started(
            start_loop.stop, d_to=dest, filename=filename
        )
        launcher.on_transfer_restarted(
            end_loop.check, d_to=dest, filename=filename
        )
        launcher.on_transfer_ended(
            end_loop.check, d_to=dest, filename=filename
        )

        src.generate(src.path('default', filename), 100)
        launcher()
        start_loop.run(timeout=10)
        launcher.kill()

        launcher()
        end_loop.run(timeout=10)

        assert src.checksum(src.path('default', filename)) == \
            dest.checksum(dest.path('default', filename))
    finally:
        try:
            src.unlink(src.path('default', filename))
            dest.unlink(dest.path('default', filename))
        except:
            pass
        launcher.close()
        pass


def test_crash_rep1_to_rep2(launcher):
    crash(launcher, 'crash_1', rep1, rep2)


def test_crash_rep2_to_rep1(launcher):
    crash(launcher, 'crash_2', rep2, rep1)
