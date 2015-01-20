# Include the Dropbox SDK libraries
from dropbox import session

# Onitu has a unique set of App key and secret to identify it.
ONITU_APP_KEY = "6towoytqygvexx3"
ONITU_APP_SECRET = "90hsd4z4d8eu3pp"

# ACCESS_TYPE should be 'dropbox' or 'app_folder' as configured for your app
ACCESS_TYPE = 'dropbox'

sess = session.DropboxSession(ONITU_APP_KEY, ONITU_APP_SECRET, ACCESS_TYPE)
request_token = sess.obtain_request_token()
url = sess.build_authorize_url(request_token)

# Make the user sign in and authorize this token
print("url: {}".format(url))
print("Please visit this website and press the 'Allow' button,"
      " then hit 'Enter' here.")
# Python 2/3 compatibility
try:
    raw_input()
except NameError:
    input()
# This will fail if the user didn't visit the above URL
access_token = sess.obtain_access_token(request_token)
# Print the token for future reference
print("Use these keys to fill your setup.yml configuration file:")
print('Access Key:', access_token.key, 'Access Secret:', access_token.secret)
