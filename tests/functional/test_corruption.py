from os import unlink
import hashlib

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import BooleanLoop, CounterLoop

launcher = None
rep1, rep2 = LocalStorageDriver('rep1'), TargetDriver('rep2')
json_file = 'test_corruption.json'


def setup_module(module):
    global launcher
    setup = Setup()
    setup.add(*rep1.setup)
    setup.add(*rep2.setup)
    setup.save(json_file)
    loop = CounterLoop(3)
    launcher = Launcher(json_file)
    launcher.on_referee_started(loop.check)
    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher()
    try:
        loop.run(timeout=5)
    except:
        teardown_module(module)
        raise


def teardown_module(module):
    launcher.kill()
    unlink(json_file)
    rep1.close()
    rep2.close()


def corruption(filename, size, newcontent):
    content_hash = hashlib.md5(newcontent).hexdigest()
    start_loop = BooleanLoop()
    launcher.on_transfer_started(
        start_loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    abort_loop = BooleanLoop()
    # If transfer is aborted, or too small and finished
    launcher.on_transfer_aborted(
        abort_loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    launcher.on_transfer_ended(
        abort_loop.stop, d_from='rep1', d_to='rep2', filename=filename
    )
    end_loop = BooleanLoop()
    launcher.on_transfer_ended(
        end_loop.stop, d_from='rep2', d_to='rep1', filename=filename
    )
    rep1.generate(filename, size)
    start_loop.run(timeout=5)
    rep2.write(filename, newcontent)
    abort_loop.run(timeout=5)
    assert rep1.checksum(filename) == rep2.checksum(filename) == content_hash


def test_corruption():
    corruption('simple', 10, 'corrupted')
