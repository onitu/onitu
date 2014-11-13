import pytest
from circus.client import CircusClient

from .setup import Setup, Rule
from .launcher import Launcher
from onitu.utils import get_circusctl_endpoint


def _get_setup(request):
    setup_func = getattr(request.module, 'setup', None)
    if setup_func is None:
        return Setup()
    return setup_func()


@pytest.fixture
def setup(request):
    return _get_setup(request)


@pytest.fixture(scope='module')
def module_setup(request):
    return _get_setup(request)


@pytest.fixture
def launcher(setup):
    return Launcher(setup)


@pytest.fixture(scope='module')
def module_launcher(module_setup):
    return Launcher(module_setup)


@pytest.fixture(scope='module')
def module_launcher_initialize(request, module_launcher):
    setup = module_launcher.setup
    setup.add(request.module.rep1)
    setup.add(request.module.rep2)
    setup.add_rule(Rule().match_path('/').sync(request.module.rep1.name,
                                               request.module.rep2.name))
    request.addfinalizer(module_launcher.close)


@pytest.fixture(scope='module')
def module_launcher_launch(module_launcher, module_launcher_initialize):
    module_launcher()


@pytest.fixture(scope='module')
def circus_client(module_setup):
    return CircusClient(endpoint=get_circusctl_endpoint(module_setup.name))
