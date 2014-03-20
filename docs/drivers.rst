=================================
Creating a new driver
=================================

A driver is a Python program that allows Onitu to synchronize files with a remote service, such as Dropbox, Google Drive, SSH, FTP or a local hard drive.

Basics
======

The drivers communicate with Onitu via the :class:`.Plug` class, which handles the operations common to all drivers. Each driver implements its specific tasks with the system of handlers_. Those handlers will be called by the :class:`.Plug` at certain occasions.

In Onitu the file transfers are made by chunks. When a new transfer begin, the :class:`.Plug` asks the others drivers for new chunks, and then call the `upload_chunk` handler.

Each driver should expose a function called `start`, which takes a name as first parameter, and returns nothing. The name is chosen by the user when he configures the driver.
This function will be called by Onitu during the initialization of the driver, and should not return until the end of life of the driver (*cf* :meth:`.Plug.listen`).

When a driver detects an update in a file, it should update the :class:`.Metadata` of the file, specify a :attr:`.Metadata.revision`, and call :meth.`.Plug.update_file`.

.. note::
  During their startup, the drivers should look for new files or updates on their remote file system. They should also listen to changes during their lifetime. The mechanism used to do that is specific to each driver, and can't be abstracted by the :class:`.Plug`.

Onitu provide a set of :ref:`functional tests <tests>` that you can use to see if your driver respond to every exigence.

.. _handlers:

Handlers
========

A handler is a function that will be called by the Plug on different occasions, such as getting a chunk from a file or starting a transfer. The drivers can define any handler they need. For example, some driver don't need to do anything for initiating a transfer, so they might not want to implement the `end_upload` handler.
In order to register a handler, the :meth:`.Plug.handler` decorator is used.

.. warning::
  All the handlers **must be thread-safe**. The plug uses several threads to handle concurrent requests, and each handler can be called from any of those threads. The :class:`.Plug` itself is fully thread-safe.

At this stage, the list of the handlers that can be defined is the following :

.. function:: get_chunk(filename, offset, size)

  Return a chunk of a given size, starting at the given offset, from a file.

  :param filename: The absolute path to the file
  :type filename: string
  :param offset: The offset from which the content should be retrieved
  :type offset: int
  :param size: The maximum size of the chunk that should be returned
  :type size: int
  :rtype: string

.. function:: upload_chunk(filename, offset, chunk)

  Write a chunk in a file at a given offset.

  :param filename: The absolute path to the file
  :type filename: string
  :param offset: The offset from which the content should be written
  :type offset: int
  :param chunk: The content that should be written
  :type chunk: string

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



The Plug
========

.. autoclass:: onitu.api.Plug
  :members:

Metadata
========

.. autoclass:: onitu.api.metadata.Metadata
  :members:

Example
=======

Usually, the drivers are created as a set of functions in a single file, with the Plug in a global variable. However, you can use a different style if you want, such as a class.

Here is an example of a simple driver working with the local file system :

.. literalinclude:: examples/driver.py
  :linenos:
