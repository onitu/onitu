Getting started with the HUBIC driver
=====================================

Run the get_refresh_token.py script in order to let Onitu gain access to your
HUBIC account.

How works the get_refresh_token.py script:

Your web browser will be launched in order to let Onitu gain access to your Hubic account.
You're going to need to input your Hubic credentials and then hit the "Accept" button.
Then, you will be redirected to a localhost address saying a problem occurred.
This is normal because you probably don't have a web server running on your machine.
There is a parameter (in the url) named code.
It is what you will need to copy/paste for the next part of this script.

The code parameter in the redirected url is after 'http://localhost/?code=' and before '&scope=...'.

Once you paste it back to the script in your terminal, it should exit after printing the refresh token you'll be able to use in your Onitu configuration.


Example
=======

An example of setup.yml configuration file set up with Hubic and Local Storage.

This will synchronize the local folder "Music" in user eric's home with the folder
eric/Music on your hubic account.

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

services:
  A:
    driver: local_storage
    folders:
      music: /home/eric/Music
      docs: /home/eric/Docs
  H:
   driver: hubic
   folders:
     music: eric/Music
   options:
     refresh_token: PLACE_REFRESH_TOKEN_HERE
     changes_timer: 10
```
