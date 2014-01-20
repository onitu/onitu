import sh
from os import unlink
from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import BooleanLoop
from utils.tempdirs import TempDirs

launcher = None
dirs = TempDirs()
json_file = 'test_startup.json'


def setup_module(module):
    global launcher
    entries = Entries()
    entries.add('local_storage', 'rep1', {'root': dirs.create()})
    entries.save(json_file)
    launcher = Launcher(json_file)
    loop = BooleanLoop()
    launcher.on_driver_started(loop.stop, 'rep1')
    launcher()
    try:
        loop.run(timeout=5)
    except:
        teardown_module(module)
        raise


def teardown_module(module):
    launcher.kill()
    unlink(json_file)


def test_all_active():
    for w in ["referee", "rep1", "redis"]:
        sh.circusctl.status(w) == "active\n"
