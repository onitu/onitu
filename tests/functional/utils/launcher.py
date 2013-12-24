import sh
import os.path

ini_name = 'onitu.ini'

def launch(directory='.'):
    return sh.circusd(os.path.join(directory, ini_name), _bg=True)
