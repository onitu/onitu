from utils import launch
from utils.entries import Entries
from utils.files import generate, checksum
from os import mkdir
import time

circus = None

def setup_module(module):
    global circus
    entries = Entries()
    entries.add('local_storage', 'rep1')
    entries.add('local_storage', 'rep2')
    # Driver should create its own directory
    entries.save('../../entries.json')
    circus = launch(directory='../..')

def teardown_module(module):
    circus.terminate()

def test_simple_copy():
    generate('../../test/driver_rep1/foo', 100)
    time.sleep(1)
    assert(checksum('../../test/driver_rep1/foo') == checksum('../../test/driver_rep1/foo'))
