import sh
from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import BooleanLoop

launcher = None
loop = BooleanLoop()


def setup_module(module):
    global launcher
    entries = Entries()
    entries.add('local_storage', 'rep1')
    entries.save('entries.json')
    launcher = Launcher()
    launcher.on_driver_started(loop.stop, 'rep1')
    launcher()


def teardown_module(module):
    launcher.kill()


def test_all_active():
    loop.run(timeout=2)
    for w in ["referee", "loader"]:
        sh.circusctl.status(w) == "active\n"
