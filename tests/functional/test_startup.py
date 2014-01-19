import sh
from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import BooleanLoop
from utils.tempdirs import TempDirs

launcher = None
loop = BooleanLoop()
dirs = TempDirs()


def setup_module(module):
    global launcher
    entries = Entries()
    entries.add('local_storage', 'rep1', {'root': dirs.create()})
    entries.save('entries.json')
    launcher = Launcher()
    launcher.on_driver_started(loop.stop, 'rep1')
    launcher()


def teardown_module(module):
    launcher.kill()


def test_all_active():
    loop.run(timeout=2)
    for w in ["referee", "rep1", "redis"]:
        sh.circusctl.status(w) == "active\n"
