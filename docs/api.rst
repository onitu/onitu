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
