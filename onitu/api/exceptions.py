"""
This module define the exceptions which can be raised inside the Plug
"""


class AbortOperation(RuntimeError):
    """
    This exception is raised in the Plug when the current
    operation should be aborted.

    Drivers should not raise this Exception, but the ones
    defined in :module:'.exceptions'.
    """
    pass


class DriverError(RuntimeError):
    """
    Base class for the exceptions raised by a Driver.

    You can raise this exception if the error comes from your Driver and
    does not correspond to the other exceptions proposed.

    You can should pass a string to the constructor describing the error.
    """
    pass


class TryAgain(DriverError):
    """
    The Plug should wait and call the handler again.

    You can should pass a string to the constructor describing the error.
    """
    pass


class ServiceError(DriverError):
    """
    The error is out of the Driver's reach, the current operation should
    be aborted.

    You can should pass a string to the constructor describing the error.
    """
    pass
