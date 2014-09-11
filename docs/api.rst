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

    GET /api/v1.0/files HTTP/1.1
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
          "fid": "10a0a66a-522b-57c6-aa96-bfba35afa12a",
          "filename": "toto",
          "size": 256,
          "owners": ["A", "B", "C"],
          "uptodate": ["A", "C"]
        },
        {
          "fid": "758644be-7d76-52f9-ad5e-add997549664",
          "filename": "photos/foo.jpg",
          "size": 12345,
          "owners": ["A", "B"],
          "uptodate": ["A", "B"]
        }
      ]
    }

  :query offset: Default to 0. The starting offset.
  :query limit: Default to 20. The maximum number of elements returned.


.. http:get:: /files/(string:fid)/metadata

  Return the metadata of a file.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1.0/files/758644be-7d76-52f9-ad5e-add997549664/metadata HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "fid": 758644be-7d76-52f9-ad5e-add997549664,
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

    GET /api/v1.0/entries HTTP/1.1
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

    GET /api/v1.0/entries/A HTTP/1.1
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

    GET /api/v1.0/entries/A/stats HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "info": {
        "age": 20.701695919036865,
        "cpu": 0.0,
        "create_time": 1406628957.07,
        "ctime": "0:00.19",
        "mem": 1.8,
        "mem_info1": "18M",
        "mem_info2": "707M",
        "started": 1406628957.370584
      },
      "name": "A",
      "status": "ok",
      "time": 1406628978.109587
    }

  **Example error**:

  .. sourcecode:: http

    HTTP/1.1 404 Not Found
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A not found",
      "status": "error",
    }

  .. sourcecode:: http

    HTTP/1.1 409 Conflict
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A is not running",
      "status": "error",
    }

.. http:get:: /entries/(name)/status

  Return the status of a given entry.

  **Example request**:

  .. sourcecode:: http

    GET /api/v1.0/entries/A/status HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "name": "A",
      "status": "active",
      "time": 1406628978.109587
    }

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "name": "A",
      "status": "stopped",
      "time": 1406628978.109587
    }

  **Example error**:

  .. sourcecode:: http

    HTTP/1.1 404 Not Found
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A not found",
      "status": "error",
    }

.. http:put:: /entries/(name)/stop

  Stop a given entry.

  **Example request**:

  .. sourcecode:: http

    PUT /api/v1.0/entries/A/stop HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "name": "A",
      "status": "ok",
      "time": 1406629516.531318
    }

  **Example error**:

  .. sourcecode:: http

    HTTP/1.1 404 Not Found
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A not found",
      "status": "error",
    }

  .. sourcecode:: http

    HTTP/1.1 409 Conflict
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A is already stopped",
      "status": "error",
    }

.. http:put:: /entries/(name)/start

  Start a given entry.

  **Example request**:

  .. sourcecode:: http

    PUT /api/v1.0/entries/A/start HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "name": "A",
      "status": "ok",
      "time": 1406629516.531318
    }

  **Example error**:

  .. sourcecode:: http

    HTTP/1.1 404 Not Found
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A not found",
      "status": "error",
    }

  .. sourcecode:: http

    HTTP/1.1 409 Conflict
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A is already running",
      "status": "error",
    }

.. http:put:: /entries/(name)/restart

  Stop and start a given entry.

  **Example request**:

  .. sourcecode:: http

    PUT /api/v1.0/entries/A/restart HTTP/1.1
    Host: 127.0.0.1
    Accept: application/json

  **Example response**:

  .. sourcecode:: http

    HTTP/1.1 200 OK
    Vary: Accept
    Content-Type: application/json

    {
      "name": "A",
      "status": "ok",
      "time": 1406629516.531318
    }

  **Example error**:

  .. sourcecode:: http

    HTTP/1.1 404 Not Found
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A not found",
      "status": "error",
    }

  .. sourcecode:: http

    HTTP/1.1 409 Conflict
    Vary: Accept
    Content-Type: application/json

    {
      "reason": "entry A is not running",
      "status": "error",
    }

Rules
-----

.. http:get:: /rules

  Get the rules

  **Example request**:

  .. sourcecode:: http

    GET /api/v1.0/rules HTTP/1.1
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

    PUT /api/v1.0/rules HTTP/1.1
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

.. http:put:: /rules/reload

  Apply the rules (if they changed since the last time)

  **Example request**:

  .. sourcecode:: http

    PUT /api/v1.0/rules/reload HTTP/1.1
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
