import sh
from utils import launch

circus = None


def setup_module(module):
    global circus
    circus = launch(directory='../..')


def teardown_module(module):
    circus.terminate()


def test_all_active():
    for w in ["referee", "A", "B", "loader"]:
        sh.circusctl.status(w) == "active\n"
