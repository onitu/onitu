Getting started with the SFTP driver
====================================

This is the driver to synchronize your SFTP server with Onitu folders.

To configure it, you'll need to put in your sftp driver configuration options:

- hostname: The hostname of your server
- port: The port of your server
- username: The username to connect with

You can connect with either your password a private key.

If you connect with your password, you'll need to provide:

- password: Your password

If you connect with a private key, you'll need to provide:

- private_key_path: The absolute path to the private key you want to use
- private_key_passphrase: The passphrase of your private key (you can omit it if your key hasn't one)

Also, be sure your public key is in your server's authorized_keys, otherwise you won't be able to connect.


Example
=======

An example Onitu setup.yml configuration file for the SFTP driver using a private key with no passphrase, on a local server with user baron_a:

```
name: example

folders:
  music:
    mimetypes:
      - "audio/*"
  docs:
    blacklist:
      - "*.bak"
      - Private/
  backup:
    blacklist:
      - ".*"
    file_size:
      max: 2G
  photos:
    mimetypes:
      - "image/*"

services:
  A:
    driver: local_storage
    folders:
      docs: /home/baron_a/Projects/EIP/onitu/example/service_a/Docs
  S:
   driver: sftp
   folders:
     docs: sftp
   options:
     hostname: localhost
     username: baron_a
     private_key_path: ~/.ssh/id_rsa
```

The start directory on connection depends on your SFTP server configuration. With default configuration, this configuration would synchronize the local folder */home/baron_a/Projects/EIP/onitu/example/service_a/Docs* with the remote folder */home/baron_a/sftp* (on a Linux server).
