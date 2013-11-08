"""
Creating a new Driver is simple. You just have to define a new module
in onitu.drivers and write a `__main__.py` for it. Your Driver must
instantiate a :class:`Plug` and call :func:`Plug.start` when it's ready
to receive the notifications from Onitu.

Your Driver must implement some handlers to respond to Onitu's requests,
see :func:`Plug.handler` for more information.
"""

from .plug import Plug
