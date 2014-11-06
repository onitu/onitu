import pytest

from .setup import Setup, Rule
from .launcher import Launcher

@pytest.fixture
def setup(request):
    setup = getattr(request.module, 'setup', None)
    if setup is not None:
        return setup
    return Setup()

@pytest.fixture
def launcher(setup):
    return Launcher(setup)

@pytest.fixture(scope='module')
def module_setup(request):
    setup = getattr(request.module, 'setup', None)
    if setup is not None:
        return setup
    return Setup()

@pytest.fixture(scope='module')
def module_launcher(module_setup):
    return Launcher(module_setup)

@pytest.fixture(scope='module')
def module_launcher_initialize(request, module_launcher):
    setup = module_launcher.setup
    setup.add(request.module.rep1)
    setup.add(request.module.rep2)
    setup.add_rule(Rule().match_path('/').sync(request.module.rep1.name, request.module.rep2.name))
    request.addfinalizer(module_launcher.close)

@pytest.fixture(scope='module')
def module_launcher_launch(module_launcher, module_launcher_initialize):
    module_launcher()
