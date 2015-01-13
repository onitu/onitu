import pytest
from circus.client import CircusClient

from onitu.utils import get_circusctl_endpoint

from .setup import Setup
from .testdriver import TestDriver


def _get_setup(request):
    setup = Setup()
    request.addfinalizer(setup.clean)
    return setup


def _get_services(request):
    get_services = getattr(request.module, 'get_services', None)
    if get_services is None:
        return TestDriver('rep1'), TestDriver('rep2')
    return get_services()


def _init_setup(request, setup):
    init_setup = getattr(request.module, 'init_setup', None)
    if init_setup is None:
        services = _get_services(request)
        for e in services:
            setup.add(e)
    else:
        init_setup(setup)


@pytest.fixture
def setup(request):
    return _get_setup(request)


@pytest.fixture(scope='module')
def module_setup(request):
    return _get_setup(request)


@pytest.fixture
def launcher(setup):
    return setup.get_launcher()


@pytest.fixture(scope='module')
def module_launcher(module_setup):
    return module_setup.get_launcher()


@pytest.fixture()
def auto_setup(request, setup):
    _init_setup(request, setup)


@pytest.fixture(scope='module')
def module_auto_setup(request, module_setup):
    _init_setup(request, module_setup)


@pytest.fixture(scope='module')
def module_launcher_launch(request, module_auto_setup, module_launcher):
    request.addfinalizer(module_launcher.close)
    module_launcher()


@pytest.fixture(scope='module')
def circus_client(module_setup):
    return CircusClient(endpoint=get_circusctl_endpoint(module_setup.name))
