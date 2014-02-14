from os import unlink
from utils.launcher import Launcher
from utils.setup import Setup
from utils.loop import CounterLoop
from utils.tempdirs import TempDirs

launcher = None
dirs = TempDirs()
json_file = 'test_startup.json'


def setup_module(module):
    global launcher
    setup = Setup()
    setup.add('local_storage', 'rep1', {'root': dirs.create()})
    setup.add('local_storage', 'rep2', {'root': dirs.create()})
    setup.save(json_file)
    launcher = Launcher(json_file)


def teardown_module(module):
    launcher.kill()
    unlink(json_file)
    dirs.delete()


def test_all_active():
    loop = CounterLoop(3)

    launcher.on_driver_started(loop.check, driver='rep1')
    launcher.on_driver_started(loop.check, driver='rep2')
    launcher.on_referee_started(loop.check)
    launcher()

    loop.run(timeout=5)

    launcher.quit()
