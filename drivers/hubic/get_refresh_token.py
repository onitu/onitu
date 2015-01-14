import requests
import urllib
import webbrowser
import base64

# Python 3 compatibility
try:
    raw_input
except NameError:
    raw_input = input

if __name__ == '__main__':

    client_id = "api_hubic_yExkTKwof2zteYA8kQG4gYFmnmHVJoNl"
    client_secret = ("CWN2NMOVwM4wjsg3RFRMmE6OpUNJhsADLaiduV4"
                     "9e7SpBsHDAKdtm5WeR5KEaDvc")
    hubic_token = "falsetoken"
    redirect_uri = "http://localhost/"

    url = "https://api.hubic.com/oauth/auth/?client_id=" + client_id
    try:
        url += "&redirect_uri=" + urllib.quote_plus(redirect_uri)
    except AttributeError:  # In python 3
        url += "&redirect_uri=" + urllib.parse.quote_plus(redirect_uri)
    url += "&scope=credentials.r&response_type=code"

    print("""We're going to start your web browser in order to let Onitu gain \
access to your Hubic account.

Then, you're going to be redirected to a localhost address. \
There will be a parameter in the URL named "code". It is between \
'http://localhost/?code=' and before '&scope=...'.

You'll have to copy/paste it for the next part of this script.

If your web browser doesn't start, access this url: {}
""".format(url))

    raw_input("If you are ready, press Enter.")
    webbrowser.open(url)
    code = raw_input("Accept Onitu and enter your code here : ")
    toEncode = "{}:{}".format(client_id, client_secret)
    try:
        application_token = base64.b64encode(toEncode)
    except TypeError:  # In Python 3
        application_token = base64.b64encode(toEncode.encode('ascii'))
        application_token = application_token.decode('utf-8')
    url = "https://api.hubic.com/oauth/token/"
    response = requests.post(
        url,
        data={
            "code": code, "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
            },
        headers={
            'Authorization': 'Basic ' + application_token
            }
        )

    if response.status_code == 400:
        raise Exception('An invalid request was submitted')
    elif not response.ok:
        raise Exception('The provided email address and/or pass are incorrect')

    hubic_refresh_token = response.json()["refresh_token"]

    print("You can now copy the following refresh token in setup.yml: {}"
          .format(hubic_refresh_token))
