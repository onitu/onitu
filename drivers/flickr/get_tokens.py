import webbrowser
from onitu_flickr import flickrapi

try:
    raw_input
except NameError:  # in python 3
    raw_input = input

api_key = '66a1c393c8de67fbeef54bb785375e06'
api_secret = '5bfbc7256872d085'
flickr = flickrapi.FlickrAPI(api_key, api_secret, format='etree')


def get_access_token():
    # Get a request token
    flickr.get_request_token(oauth_callback="oob")

    print("""In order to use Flickr with Onitu, you're going to need to let \
    the Onitu Flickr app gain access to your Flickr account.

    To do so, the script is going to open a window in your web browser to the \
    Flickr website where you'll have to copy/paste a verification code back \
    here in the terminal.
    """)

    raw_input("If you're ready, press Enter.")
    # Open a browser at the authentication URL. Do this however
    # you want, as long as the user visits that URL.
    authorize_url = flickr.auth_url(perms='delete')
    webbrowser.open(authorize_url)

    # Get the verifier code from the user. Do this however you
    # want, as long as the user gives the application the code.
    verifier = raw_input("Paste the code here: ")

    try:
        verifier = unicode(verifier)
    except NameError:  # in python 3
        # No unicode type, but that's ok, that's what the next function wants
        pass
    # Trade the request token for an access token
    flickr.get_access_token(verifier)


if not flickr.token_valid(perms='delete'):
    get_access_token()

print("You can use the following tokens in your Onitu setup.yml file: {} {}"
      .format(flickr.token_cache.token.token,
              flickr.token_cache.token.token_secret))
