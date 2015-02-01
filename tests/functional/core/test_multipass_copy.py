import pytest

from tests.utils.testdriver import TestDriver
from tests.utils.loop import BooleanLoop


def get_services():
    return TestDriver('rep1'), TestDriver('rep2', speed_bump=True)


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def test_multipass_copy(module_launcher):
    src, dest = module_launcher.get_services('rep1', 'rep2')
    count = 10
    size = 100
    filename = 'multipass'

    startloop = BooleanLoop()
    loop = BooleanLoop()

    module_launcher.on_transfer_started(
        startloop.stop, d_to=dest, filename=filename,
        unique=False
    )
    module_launcher.on_transfer_ended(
        loop.stop, d_to=dest, filename=filename, unique=False
    )
    module_launcher.on_transfer_aborted(
        loop.stop, d_to=dest, filename=filename, unique=False
    )

    src.generate(src.path('default', filename), size)
    startloop.run(timeout=2)

    for _ in range(count):
        startloop.restart()
        loop.restart()
        src.generate(src.path('default', filename), size)
        loop.run(timeout=5)
        startloop.run(timeout=2)
    loop.restart()
    loop.run(timeout=5)

    assert src.checksum(src.path('default', filename)) == \
        dest.checksum(dest.path('default', filename))
