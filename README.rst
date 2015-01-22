|Onitu|
=======

Onitu - Sync and share your files from various services and backends

Installing
-----------
Onitu has two binary dependencies: ZeroMQ and Leveldb. Make sure to install them before installing Onitu.

To install Onitu locally (in a virtualenv for instance), execute the following commands:
::
    $ git clone git@github.com:onitu/onitu.git
    $ cd onitu
    $ pip install -r requirements.txt

Then, you can start using onitu with the ``onitu`` command.

Tests and Benchmarks |Build Status| |Landscape|
-----------------------------------

::

    $ py.test -v tests/functionnal # test within your current env
    $ tox -e py2.7 # test with python2.7
    $ tox -e flake8 # check syntax
    $ tox -e benchmarks # run the benchmarks

.. |Onitu| image:: logo.png
.. |Build Status| image:: https://travis-ci.org/onitu/onitu.png?branch=develop
   :target: https://travis-ci.org/onitu/onitu
.. |Landscape| .. image:: https://landscape.io/github/onitu/onitu/develop/landscape.svg
   :target: https://landscape.io/github/onitu/onitu/develop
   :alt: Code Health
