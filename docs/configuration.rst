==================
Configuration file
==================

.. warning::
   This documentation describes a proposal for the next format of Onitu's configuration. Curently the setup is done is JSON and is nothing like what is described here.

Onitu's configuration file is YAML.

Layout
======

A configuration file is mainly concerned with Folders and Services.

Folders are named directories that Onitu knows of and are considered roots of their respective hierarchies. Each folder will be kept syncronised across the different places it is mapped.

Services are configured drivers. A driver can be configured several times, thus producing more than one service. For exemple one could have two services, each controling a different remote server using the same driver.

The configuration file is meant to configure the services, map folders to services and control the way they are syncronised. All folders are first listed in the configuration and folder options can be used to specify how exactly they should be treated. Then all services are listed with their configuration. For each one of them the folders that should be mapped on this service are also listed. Additional options can be specified for each folder in a service. Those are the same than those used on folders or services but are used when when a more specific configuration is desiredon on per service-folder basis.

.. literalinclude:: sample_confs/layout.yaml
  :linenos:

Folder options
==============

mode
  :values:
     "r", "w", "rw"
  :default:
     "rw"
  :what:
     This value indicates if the folder should only be read-from, written-to or if it should be syncronised both ways. You probably want to specify this at the service level and not at the folder level.

     :r (read):
	If not specified new files or changes made in this folder will not be taken into account. You must specify this if you want Onitu to be able to read content from this folder.
     :w (write):
	If not specified new files or changes will not be written to this folder. You must specify this if you want Onitu to make changes to this folder when syncronising.

type
  :values:
     To be defined. One or more media types as defined in rfc6838. Incomplete types such as "example" instead of "example/media_type" should be accepted.
  :default:
     If not specified all types will be accepted.
  :what:
     This value restricts which type(s) of file should be accepted in this folder. Files not conforming to this value will never be read from or written to this folder.

min-size, max-size
  :values:
     A numeric value with an optional multiplying sufix. Metric prefixes (k, M, G, T, P)  and IEC prefixes (Ki, Mi, Gi, Ti, Pi) are accepted.
  :default:
     If min-size is not specified there is no limit on how big a file in this folder must be. If max-siz is not specified there is no limit on how big a file in this folder can be.
  :what:
     This value restricts which files should be accepted in this folder based on their size. Files not within the range specified by min-size and max-size will never be read from or written to this folder.

blacklist, whitelist
  :values:
     A list of paths, shell-like globbing is allowed.
  :default:
     By default the blacklist is empty and the whitelist isn't used if not specified or empty. (To disable syncronisation completly you should use the folder's mode.)
  :what:
     Only files matching a pattern in the whitelist will be accepted in this folder. Files matching a pattern in the blacklist will never be accepted.


Example configuration
=====================

This are sample configuration using some of the folder options above and some simple service options. More information about service options can be found in the section bellow. Those sample files are to give an idea of how folder options can be used to achieve different kinds of synchronisation, they are not about illustrating the different service options.

.. literalinclude:: sample_confs/sample.yaml
  :linenos:


Service options
===============

Service options are specific to each driver. This is because different drivers need to know different things to be able to handle their backends. This is a list of options for each driver.

TODO: Describe options for each driver.
