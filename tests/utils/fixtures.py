import pytest
from circus.client import CircusClient

from .setup import Setup, Rule
from onitu.utils import get_circusctl_endpoint


def _get_setup(request):
    get_setup = getattr(request.module, 'get_setup', None)
    if get_setup is None:
        setup = Setup()
    else:
        setup = get_setup()
    request.addfinalizer(setup.clean)
    return setup


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


@pytest.fixture(scope='module')
def module_setup_initialize(request, module_setup):
    module_setup.add(request.module.rep1)
    module_setup.add(request.module.rep2)
    rule = Rule().match_path('/').sync(request.module.rep1.name,
                                       request.module.rep2.name)
    module_setup.add_rule(rule)


@pytest.fixture(scope='module')
def module_launcher_launch(request, module_setup_initialize, module_launcher):
    request.addfinalizer(module_launcher.close)
    module_launcher()


@pytest.fixture(scope='module')
def circus_client(module_setup):
    return CircusClient(endpoint=get_circusctl_endpoint(module_setup.name))
