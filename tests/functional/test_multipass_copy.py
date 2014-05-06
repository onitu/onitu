from os import unlink

from tests.utils.launcher import Launcher
from tests.utils.setup import Setup, Rule
from tests.utils.driver import LocalStorageDriver, TargetDriver
from tests.utils.loop import BooleanLoop, CounterLoop
from tests.utils.files import KB

launcher = None
rep1, rep2 = LocalStorageDriver('rep1', chunk_size=1), TargetDriver('rep2')
json_file = 'test_multipass_copy.json'


def setup_module(module):
    global launcher
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
    unlink(json_file)
    rep1.close()
    rep2.close()


def test_multipass_copy():
    count = 10
    filename = 'multipass'

    loop_end, loop_abort = BooleanLoop(), BooleanLoop()

    launcher.on_transfer_ended(
        loop_end.stop, d_from='rep1', d_to='rep2', filename=filename,
        unique=False
    )
    launcher.on_transfer_aborted(
        loop_abort.stop, d_from='rep1', d_to='rep2', filename=filename,
        unique=False
    )

    rep1.generate(filename, 100 * KB)

    for _ in range(count):
        rep1.generate(filename, 100 * KB)
        loop_abort.run(timeout=2)
    loop_end.run(timeout=5)

    assert rep1.checksum(filename) == rep2.checksum(filename)
