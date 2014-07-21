=================================
API 1.0
=================================

Overview
========

The port used by the API is **3862**. All data is sent and received as JSON, and using the UTF-8 charset.

Routes
======

.. note::
  All the following routes must be prefixed by : `/api/v1.0`.

Files
-----

.. http:get:: /files

  List the files.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/files HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "files": [
        {
          "fid": 1,
          "filename": "toto",
          "size": 256,
          "owners": ["A", "B", "C"],
          "uptodate": ["A", "C"]
        },
        {
          "fid": 2,
          "filename": "photos/foo.jpg",
          "size": 12345,
          "owners": ["A", "B"],
          "uptodate": ["A", "B"]
        }
      ]
    }

  :query offset: Default to 0. The starting offset.
  :query limit: Default to 20. The maximum number of elements returned.


.. http:get:: /files/(int:id)/metadata

  Return the metadata of a file.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/files/1/metadata HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "fid": 1,
      "filename": "toto",
      "size": 256,
      "owners": ["A", "B", "C"],
      "uptodate": ["A", "C"]
    }

Entries
-------

.. http:get:: /entries

  List all the entries.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/entries HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "entries": [
        {
          "name": "A",
          "driver": "local_storage",
          "options": {
            "root": "example/A"
          }
        },
        {
          "name": "B",
          "driver": "local_storage",
          "options": {
            "root": "example/B"
          }
        }
      ]
    }


.. http:get:: /entries/(name)

  Return the description of a given entry.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/entries/A HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "name": "A",
      "driver": "local_storage",
      "options": {
        "root": "example/A"
      }
    }

.. http:get:: /entries/(name)/stats

  Return the stats of a given entry (age, cpu, memory, status, name).

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/entries/A/stats HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "id": "63e6871d460647e8ace77419da7ab8fe",
      "info": {
        "3203": {
          "age": 93.51760005950928,
          "cpu": 0.2,
          "create_time": 1405773648.99,
          "ctime": "0:00.46",
          "mem": 1.8,
          "mem_info1": "18M",
          "mem_info2": "707M",
          "started": 1405773649.262883,
        }
      },
      "name": "a",
      "status": "ok",
      "time": 1405773742.817528
    }

.. http:get:: /entries/(name)/stop

  Stop a given entry.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/entries/A/stop HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "status": "ok"
    }

.. http:get:: /entries/(name)/start

  Start a given entry.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/entries/A/start HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "status": "ok"
    }

.. http:get:: /entries/(name)/restart

  Stop and start a given entry.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/entries/A/restart HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "status": "ok"
    }

Rules
-----

.. http:get:: /rules

  Get the rules

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/rules HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "rules": [
        {
          "match": {"path": "/"},
          "sync": ["A"]
        },
        {
          "match": {"path": "/backedup/", "mime": ["application/pdf"]},
          "sync": ["B"]
        }
      ]
    }

.. http:put:: /rules

  Update the rules

  **Example request**:

  .. sourcecode:: http

    PUT /api/v1/rules HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

    {
      "rules": [
        {
          "match": {"path": "/"},
          "sync": ["A"]
        },
        {
          "match": {"path": "/backedup/", "mime": ["application/pdf"]},
          "sync": ["B"]
        }
      ]
    }

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "status": "ok"
    }

.. http:get:: /rules/reload

  Apply the rules (if they changed since the last time)

  **Example request**:

  .. sourcecode:: http

    GET /api/v1/rules/reload HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "status": "ok"
    }
