import sh
from utils import launch
from time import sleep

circus = None


def setup_module(module):
    global circus
    circus = launch(directory='../..')


def teardown_module(module):
    circus.terminate()


def test_all_active():
    sleep(1)
    for w in ["referee", "A", "B", "loader"]:
        sh.circusctl.status(w) == "active\n"
