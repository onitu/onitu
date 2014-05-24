import hashlib

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import BooleanLoop, CounterLoop

launcher, setup = None, None
# We use chunks of size 1 to slow down the transfers. This way, we have
# more chances to stop a transfer before its completion
rep1 = LocalStorageDriver('rep1', chunk_size=1)
rep2 = TargetDriver('rep2', chunk_size=1)
json_file = 'test_corruption.json'


def setup_module(module):
    global launcher, setup
    setup = Setup()
    setup.add(rep1)
    setup.add(rep2)
    setup.add_rule(Rule().match_path('/').sync(rep1.name, rep2.name))
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
    setup.clean()


def corruption(filename, size, newcontent):
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


def test_corruption():
    corruption('simple', 100, 'corrupted')
