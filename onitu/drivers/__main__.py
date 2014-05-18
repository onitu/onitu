import os
import sys
import json
import importlib

from logbook import error
from logbook.queues import ZeroMQHandler

driver_name = sys.argv[1]
name = sys.argv[2]
log_uri = sys.argv[3]

driver = importlib.import_module('.' + driver_name, package='onitu.drivers')

path = os.path.dirname(__file__)

try:
    with open(os.path.join(path, driver_name, 'manifest.json')) as f:
        manifest = json.load(f)
except ValueError as e:
    error("Error parsing the manifest file of {} : {}", name, e)
    exit(-1)
except Exception as e:
    error(
        "Cannot open the manifest file of '{}' : {}", name, e
    )
    exit(-1)

with ZeroMQHandler(log_uri, multi=True).applicationbound():
    try:
        driver.plug.initialize(name, manifest)
        del manifest

        driver.start()
    except Exception as e:
        error("Error in '{}': {}", name, e)
