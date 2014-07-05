import os
import sys
import json
import importlib

from threading import Thread

from logbook import error
from logbook.queues import ZeroMQHandler

from onitu.utils import at_exit

driver_name = sys.argv[1]
escalator_uri = sys.argv[2]
session = sys.argv[3]
name = sys.argv[4]
log_uri = sys.argv[5]

driver = importlib.import_module('.' + driver_name, package='onitu.drivers')

at_exit(driver.plug.close)

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
        driver.plug.initialize(name, escalator_uri, session, manifest)
        del manifest

        thread = Thread(target=driver.start)
        thread.start()

        while thread.is_alive():
            thread.join(100)
    except Exception as e:
        error("Error in '{}': {}", name, e)

    driver.plug.logger.info("Exited")
