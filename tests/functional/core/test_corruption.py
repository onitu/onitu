import hashlib

import pytest

from tests.utils.driver import TestingDriver
from tests.utils.loop import BooleanLoop

# We use chunks of size 1 to slow down the transfers. This way, we have
# more chances to stop a transfer before its completion
rep1 = TestingDriver('rep1')
rep2 = TestingDriver('rep2', speed_bump=True)


@pytest.fixture(autouse=True)
def _(module_launcher_launch):
    pass


def corruption(launcher, filename, size, newcontent):
    content_hash = hashlib.md5(newcontent.encode()).hexdigest()
    start_loop = BooleanLoop()
    launcher.on_transfer_started(
        start_loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    end_loop = BooleanLoop()
    launcher.on_transfer_ended(
        end_loop.stop, d_from='rep2', d_to='rep1', filename=filename
    )
    rep1.generate(filename, size)
    start_loop.run(timeout=5)
    rep2.write(filename, newcontent)
    end_loop.run(timeout=5)
    assert rep1.checksum(filename) == rep2.checksum(filename) == content_hash


def test_corruption(module_launcher):
    corruption(module_launcher, 'simple', 100, 'corrupted')
