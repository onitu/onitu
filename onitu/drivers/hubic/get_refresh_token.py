import requests
import urllib
import webbrowser
import base64

if __name__ == '__main__':

    client_id = ""
    client_secret = ""
    hubic_token = "falsetoken"
    redirect_uri = "http://localhost/"

    url = "https://api.hubic.com/oauth/auth/?client_id=" + client_id
    url += "&redirect_uri=" + urllib.quote_plus(redirect_uri)
    url += "&scope=credentials.r&response_type=code"

    print "Your web browser will be launched and you must accept onitu."
    print "Then, you will be redirected to a localhost adress."
    print "There is a parameter (in the url) named \"code\"."
    print "You will need to copy/paste it for the next part of this script."

    raw_input("If you are ready press enter.")
    webbrowser.open(url)
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
    print "Please copy this code in setup.json: " + hubic_refresh_token
