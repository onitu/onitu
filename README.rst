|Onitu|
=======

Onitu - Sync and share your files from various services and backends

/!\\ Abandoned /!\\
-----------------
Unfortunately, this project is no longer maintained. It started as a student project and we don't feel like pushing it forward anymore.

Onitu was a great experience, and we encountered many challenges during its development: interacting with many third-party (bogus) APIs, managing a highly concurrent workflow,  handling events from a filesystem in near real-time, and providing an easy installation on several platforms.
Some of these challenges were manageable but others were out of reach, making Onitu everything but stable.

We don't think that any project has reached all of Onitu's goals. However, there are plenty of amazing solutions out there with a different scope. Here is a non-exhaustive list of Open-Source projects we love:

- `Cozy <http://cozy.io/>`_
- `Owncloud <https://owncloud.org/>`_
- `Syncany <https://www.syncany.org/>`_
- `SparkleShare <http://sparkleshare.org/>`_
- `Syncthing <http://syncthing.net>`_
- `Pydio <https://pyd.io/>`_

Feel free to contact us if you have any question. You can reach us by mail (onitu_2015@labeip.epitech.eu), in the issues, or on IRC at #onitu on irc.freenode.org.

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
.. |Landscape| image:: https://landscape.io/github/onitu/onitu/develop/landscape.svg
   :target: https://landscape.io/github/onitu/onitu/develop
   :alt: Code Health
