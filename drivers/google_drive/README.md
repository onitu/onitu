Getting started with the Google Drive driver
============================================

Run the get_access_token.py script in order to get the token used by Onitu to connect to your Google Drive account.
Get the token refresh provided by the script and put it in your `setup.json` as described bellow.

Google Drive Driver
===================

This is the Onitu driver for the Google Drive Storage, allowing you to sync your files between your Google Drive account and Onitu.

First, you need to generate your access tokens in order to allow Onitu to access your account.

To do that, we provide a script called `get_access_token.py` that generates for you the URL you need to visit.
Just run `python get_access_token.py` in a terminal, and go to the generated URL. Then, follow the instructions from the script.

Once you got your Refresh Token from the script, you need to create a new driver entry in the setup JSON file (setup.json), and fill in the following fields:
- driver : this should always be "google_drive"
- options: The following options can be used:
  - `root`: The folder under which you want Onitu to put all the transferred files on your Google Drive. Onitu won't put files elsewhere. If you want to use the whole Google Drive, omit it or set ""
  - `refresh_token`: The Refresh Token given by `get_access_token.py` script
  - changes_timer: Onitu periodically checks for changes on Google Drive. Use this to set a period of time, in seconds, between each retry. Defaults to 1 minute (60 seconds) if you omit it.

A correct syntax for the entry could be the following:

```json
    "drive": {
      "driver": "google_drive",
      "options": {
        "root": "/onitu",
        "refresh_token": "XXXXXXXXXXXXXXXXX",
	"changes_timer" : 60
      }
    }
```

Then, to synchronize a folder with Google Drive, e.g. the "gdrive/" folder, add this to your rules:

```json
    {
      "match": {"path": "/gdrive/"},
      "sync": ["drive"]
    }
```

This will sync the gdrive/ folder with the driver named drive.
