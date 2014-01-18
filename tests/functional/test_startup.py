import sh
from utils.launcher import Launcher
from utils.entries import Entries
from utils.loop import EventLoop

circus = None
loop = EventLoop()


def setup_module(module):
    global circus
    entries = Entries()
    entries.add('local_storage', 'rep1')
    entries.save('entries.json')
    launcher = Launcher()
    launcher.set_event(launcher.on_driver_started('rep1'), loop.stop)
    circus = launcher()


def teardown_module(module):
    circus.terminate()


def test_all_active():
    loop.run()
    for w in ["referee", "loader"]:
        sh.circusctl.status(w) == "active\n"
