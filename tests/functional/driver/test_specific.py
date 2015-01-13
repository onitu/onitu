from tests.utils.targetdriver import TargetModule

if hasattr(TargetModule, 'driver_tests'):
    tests = TargetModule.driver_tests
    for attr in dir(tests):
        if attr.startswith('__'):
            continue
        locals()[attr] = getattr(tests, attr)
