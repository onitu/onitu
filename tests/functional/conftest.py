from os import chdir


def pytest_configure(config):
    chdir('../..')
