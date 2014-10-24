Getting started with the Google Drive driver
============================================

Run the get_access_token.py script in order to let Onitu gain access to your
Google Drive account.

Retrieve the token refresh provided by the script and put it in
Onitu's setup.json for Onitu to use it to authenticate itself with the Drive API.

Google Drive Driver
===================

This is the Onitu driver for the Google Drive Storage. It permits to sync Onitu with your Drive account.

Google Drive uses OAuth2 to authenticate the user behind an application wanting to use it.
Hence, to let Onitu authenticate itself to Google Drive, you're going to need to generate OAuth tokens.

To do that, we provide a script called get_access_token.py that generates for you the URL you need to go to to allow Google Drive use for Onitu.
Just run "python get_access_token.py" in a terminal, and go to the generated URL. Once you did it, come back to the terminal and follow the instructions.

The script will then provide you an "Refresh Token". They are the codes you'll need to use with Onitu.

Once you have them, you need to create a new driver entry in the setup JSON file (setup.json), and fill in the following fields:
- driver : this should always be "google_drive"
- options: The following options can be used:
  - root: The folder under which you want Onitu to put all the transferred files on your Google Drive. Onitu won't put files elsewhere. If you want to use the whole Google Drive, omit it or set ""
  - client_id: Id Client of onitu driver app for Google Drive. You don't need to change it
  - client_secret: Secret Client of onitu driver app for Google Drive. You don't need to change it
  - refresh_token: Put here the token give by get_access_token script
  - changes_timer: Onitu periodically checks for changes on Google Drive. Use this to set a period of time, in seconds, between each retry. Defaults to 1 minute (60 seconds) if you omit it.

A correct syntax for the entry could be the following:
    "drive": {
      "driver": "google_drive",
      "options": {
        "root": "/onitu",
        "client_id": "6155769202.apps.googleusercontent.com",
        "client_secret": "ZcxluuTcGL2WkurnYSJgJvbN",
        "refresh_token": "",
	      "changes_timer" : 60
      }
    }

Then, to synchronize a folder with Google Drive, e.g. the "gdrive/" folder, add this to your rules:

    {
      "match": {"path": "/gdrive/"},
      "sync": ["drive"]
    }

This will sync the gdrive/ folder with the driver named drive.
