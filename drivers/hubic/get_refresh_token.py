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
    url += "&redirect_uri=" + urllib.quote_plus(redirect_uri)
    url += "&scope=credentials.r&response_type=code"

    print
    print "Your web browser will be launched in order to let Onitu gain "
    "access to your Hubic account.."
    print "Then, you will be redirected to a localhost address."
    print "There is a parameter (in the url) named \"code\"."
    print "You will need to copy/paste it for the next part of this script."
    print
    print "If your web browser doesn't start, access this url:"
    print url
    print

    raw_input("If you are ready press enter.")
    webbrowser.open(url)
    print
    print "The code parameter in the redirected url is after "
    "'http://localhost/?code=' and before '&scope=...'"
    print
    code = raw_input("Accept Onitu and enter your code here : ")

    application_token = base64.b64encode(client_id + ":" + client_secret)
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

    print
    print "You can now copy the following refresh token in setup.json"
    print hubic_refresh_token
    print
