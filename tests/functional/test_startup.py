import sh

circus = None

def setup_module(module):
    global circus
    circus = sh.circusd('onitu.ini', _bg=True)


def teardown_module(module):
    circus.terminate()


def test_all_active():
    for w in ["referee", "A", "B", "loader"]:
        sh.circusctl.status(w) == "active\n"
