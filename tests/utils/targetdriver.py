import os

from .driver import load_driver


TargetDriver = load_driver(os.environ.get('ONITU_TEST_DRIVER', 'test'))
