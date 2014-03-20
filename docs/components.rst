=================================
Components documentation
=================================

Here is the documentation of the parts not covered yet. You should not have to worry about those parts if you are writing a new driver, but they can be very useful if you want to hack the core of Onitu.

Launcher
============

.. automodule:: onitu.__main__
  :members:

Referee
=======

The role of the Referee is to receive the events emitted by the drivers, and to send notifications to the other drivers accordingly to the configuration rules.

.. autoclass:: onitu.referee.Referee
  :members:

Utils
=====

.. automodule:: onitu.utils
  :members:
