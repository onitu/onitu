import sys
import json
from threading import Thread

from logbook import error
from logbook.queues import ZeroMQHandler

from onitu.utils import at_exit, get_available_drivers

driver_name = sys.argv[1]
escalator_uri = sys.argv[2]
session = sys.argv[3]
name = sys.argv[4]
log_uri = sys.argv[5]

drivers = get_available_drivers()


if driver_name not in drivers:
    error("Driver {} not found.", driver_name)
    exit(-1)

try:
    entry_point = drivers[driver_name]
    driver = entry_point.load()
except ImportError as e:
    error("Error importing driver {}: {}", driver_name, e)
    exit(-1)

if 'start' not in driver.__all__:
    error("Driver {} is not exporting a start function.", driver_name)
    exit(-1)

if 'plug' not in driver.__all__:
    error("Driver {} is not exporting a Plug instance.", driver_name)
    exit(-1)

at_exit(driver.plug.close)


try:
    # Using get_resource_stream doesn't seem to be working on Python 3 as
    # it returns bytes
    content = entry_point.dist.get_resource_string('', 'manifest.json')
    manifest = json.loads(content.decode('utf-8'))
except ValueError as e:
    error("Error parsing the manifest file of {} : {}", name, e)
    exit(-1)
except (IOError, OSError) as e:
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
