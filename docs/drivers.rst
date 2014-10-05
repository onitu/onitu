=================================
Creating a new driver
=================================

A driver is a Python program which allows Onitu to synchronize files with a remote service, such as Dropbox, Google Drive, SSH, FTP or a local hard drive.

Basics
======

The drivers communicate with Onitu via the :class:`.Plug` class, which handles the operations common to all drivers. Each driver implements its specific tasks with the system of handlers_. Those handlers will be called by the :class:`.Plug` at certain occasions.

In Onitu the file transfers can be made by chunks. When a new transfer begin, the :class:`.Plug` asks the others drivers for new chunks, and then call the `upload_chunk` handler. The transfers can also be made via the `upload_file` handler, which upload the full content of the file. Both protocols can be used together.

Each driver must expose a function called `start` and an instance of the :class:`.Plug` in their `__init__.py` file. This `start` function will be called by Onitu during the initialization of the driver, and should not return until the end of life of the driver (*cf* :meth:`.Plug.listen`).

When a driver detects an update in a file, it should update the :class:`.Metadata` of the file, specify a :attr:`.Metadata.revision`, and call :meth:`.Plug.update_file`.

.. note::
  During their startup, the drivers should look for new files or updates on their remote file system. They should also listen to changes during their lifetime. The mechanism used to do that is specific to each driver, and can't be abstracted by the :class:`.Plug`.

Each driver must have a manifest_ describing its purpose and its options.

Onitu provide a set of :ref:`functional tests <tests>` that you can use to see if your driver respond to every exigence.

.. _handlers:

Handlers
========

A handler is a function that will be called by the Plug on different occasions, such as getting a chunk from a file or starting a transfer. The drivers can define any handler they need. For example, some driver don't need to do anything for initiating a transfer, so they might not want to implement the `end_upload` handler.
In order to register a handler, the :meth:`.Plug.handler` decorator is used.

.. warning::
  All the handlers **must be thread-safe**. The plug uses several threads to handle concurrent requests, and each handler can be called from any of those threads. The :class:`.Plug` itself is fully thread-safe.

At this stage, the list of the handlers that can be defined is the following :

.. function:: get_chunk(metadata, offset, size)

  Return a chunk of a given size, starting at the given offset, from a file.

  :param metadata: The metadata of the file
  :type metadata: :class:`.Metadata`
  :param offset: The offset from which the content should be retrieved
  :type offset: int
  :param size: The maximum size of the chunk that should be returned
  :type size: int
  :rtype: string

.. function:: get_file(metadata)

  Return the full content of a file.

  :param metadata: The metadata of the file
  :type metadata: :class:`.Metadata`
  :rtype: string

.. function:: upload_chunk(metadata, offset, chunk)

  Write a chunk in a file at a given offset.

  :param metadata: The metadata of the file
  :type metadata: :class:`.Metadata`
  :param offset: The offset from which the content should be written
  :type offset: int
  :param chunk: The content that should be written
  :type chunk: string

.. function:: upload_file(metadata, content)

  Write the full content of a file.

  :param metadata: The metadata of the file
  :type metadata: :class:`.Metadata`
  :param content: The content of the file
  :type chunk: string

.. function:: set_chunk_size(chunk_size)

  Allows a driver to force a chunk size by overriding the default, or provided, value.
  The handler takes the plug chunk size as argument, and if that size is invalid for the driver, it can return a new value.
  Useful for services that require a minimum size for transfers.

  :param chunk_size: the size the plug is currently using
  :type chunk_size: int

.. function:: start_upload(metadata)

  Initialize a new upload. This handler is called when a new transfer is started.

  :param metadata: The metadata of the file transferred
  :type metadata: :class:`.Metadata`

.. function:: restart_upload(metadata, offset)

  Restart a failed upload. This handler will be called during the startup if a transfer has been stopped.

  :param metadata: The metadata of the file transferred
  :type metadata: :class:`.Metadata`
  :param offset: The offset of the last chunk uploaded
  :type offset: int

.. function:: end_upload(metadata)

  Called when a transfer is over.

  :param metadata: The metadata of the file transferred
  :type metadata: :class:`.Metadata`

.. function:: abort_upload(metadata)

  Called when a transfer is aborted. For example, this could happen if a newer version of the file should be uploaded during the transfer.

  :param metadata: The metadata of the file transferred
  :type metadata: :class:`.Metadata`


.. function:: close()

  Called when Onitu is closing. This gives a chance to the driver to clean its resources. Note that it is called from a sighandler, so
  some external functionalities might not work as expected. This handler should not take too long to complete or it could cause
  perturbations.


The Plug
========

.. autoclass:: onitu.plug.Plug
  :members:

Metadata
========

.. autoclass:: onitu.plug.metadata.Metadata
  :members:

Exceptions
==========

If an error happen in a driver, it should raise an appropriate exception. Two exceptions are handled by the :class:`.Plug`, and should be used accordingly to the situation : :class:`.DriverError` and :class:`.ServiceError`.

.. autoclass:: onitu.api.exceptions.DriverError

.. autoclass:: onitu.api.exceptions.ServiceError


.. _manifest:

Manifest
========

A manifest is a JSON file describing a driver in order to help the users configuring it. It contains several informations, such as the name of the driver, its description, and its available options. Each option must have a name, a description and a type.

The type of the options will be used by Onitu to validate them, and by the interface in order to offer a proper input field. The available types are : Integers, Floats, Booleans, Strings and Enumerates. An enumerate type must add a `values` field with the list of all the possible values.

An option can have a `default` field which represents the default value (it can be `null`). If this field is present, the option is not mandatory. All the options without a default value are mandatory.

Here is an example of what your manifest should look like :

.. literalinclude:: examples/manifest.json

Example
=======

Usually, the drivers are created as a set of functions in a single file, with the Plug in a global variable. However, you can use a different style if you want, such as a class.

Here is an example of a simple driver working with the local file system :

.. literalinclude:: examples/driver.py
  :linenos:

This is what a driver's `__init__.py` file should look like:

.. literalinclude:: examples/init_driver.py
  :linenos:
