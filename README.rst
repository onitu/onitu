|Onitu|
=======

Onitu - Sync and share your files from various services and backends

Installing
-----------
Onitu as two binary dependencies: ZeroMQ and Leveldb. Make sure to install them before installing Onitu.

To install Onitu locally (in a virtualenv for instance), execute the following commands:
::
    $ git clone git@github.com:onitu/onitu.git
    $ cd onitu
    $ pip install -r requirements.txt

Then, you can start using onitu with the ``onitu`` command.

Tests and Benchmarks |Build Status|
-----------------------------------

::

    $ py.test -v tests/functionnal # test whithin your current env
    $ tox -e py2.7 # test with python2.7
    $ tox -e flake8 # check syntaxe
    $ tox -e benchmarks # run the benchmarks

.. |Onitu| image:: logo.png
.. |Build Status| image:: https://travis-ci.org/onitu/onitu.png?branch=develop
   :target: https://travis-ci.org/onitu/onitu
