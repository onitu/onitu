Getting started with the Dropbox driver
=======================================

Run the get_access_token.py script in order to let Onitu gain access to your
Dropbox account.

Retrieve the access key and secret provided by the script and put it in Onitu's configuration file for Onitu to use it to authenticate itself with the Dropbox Core API.

Dropbox Driver
==============

This is the Onitu driver for the Dropbox cloud service. It permits to sync Onitu with your Dropbox account.

Dropbox uses OAuth to authenticate the user behind an application wanting to use it.
Hence, to let Onitu authenticate itself to Dropbox, you're going to need to generate OAuth tokens.

To do that, we provide a script called get_access_token.py that generates for you the URL you need to go to to allow Dropbox use for Onitu.
Just run "python get_access_token.py" in a terminal, and go to the generated URL. Once you did it, come back to the terminal and follow the instructions.

*Warning:* Be advised that due to Dropbox SDK limitations, the get_access_token.py script doesn't work with Python 3.x. We advise running it with Python 2.7.

The script will then provide you an "Access Key" and an "Access Secret". They are the codes you'll need to use with Onitu.

Once you have them, you need to create a new driver service in the setup YAML file (setup.yml). Create a new service using driver "dropbox", and fill the following
fields in its "options" section:
  - access_key: Put here your Access Key
  - access_secret: Put here your Access Secret
  - changes_timer: Onitu periodically checks for changes on Dropbox. Use this to set a period of time, in seconds, between each retry.
    		   Defaults to 1 minute (60 seconds) if you omit it.


Example
=======

This is an example YAML setup using a local storage driver and a Dropbox driver properly set up to share folders:
"
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

services:
  A:
    driver: local_storage
    folders:
      music: /home/baron_a/Music
      docs: /home/baron_a/Docs
  D:
    driver: dropbox
    folders:
      music: /pando/Music
      docs: /pando/Docs
    options:
        access_key: INSERT_ACCESS_KEY_HERE
        access_secret: INSERT_ACCESS_SECRET_HERE
        changes_timer: 10
"

It will synchronize the local folders /home/baron_a/Music and /home/baron_a/Docs with their Dropbox counterparts, /pando/Music and /pando/Docs.