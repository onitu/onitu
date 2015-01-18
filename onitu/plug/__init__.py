import os

if 'ONITU_CLIENT' in os.environ:
    from .client import Plug, DriverError, ServiceError
else:
    from .plug import Plug
    from .exceptions import DriverError, ServiceError

__all__ = ['Plug', 'DriverError', 'ServiceError']
