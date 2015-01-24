# -*- coding: utf-8 -*-

import requests
import json
import sys
if sys.version_info[:2] <= (2, 7):
    from urllib import urlencode
else:
    from urllib.parse import urlencode

client_id = "6155769202.apps.googleusercontent.com"
client_secret = "ZcxluuTcGL2WkurnYSJgJvbN"
redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
base_url = r"https://accounts.google.com/o/oauth2/"
authorization_code = ""
refresh_token = ""


"""
Retrieving authorization_code from authorization API.
"""


def retrieve_authorization_code():
    authorization_code_req = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": (r"https://www.googleapis.com/auth/drive")
        }
    r = requests.get(base_url
                     + "auth?{}".format(urlencode(authorization_code_req)),
                     allow_redirects=False)
    print("Please go to this url and accept the application.")
    url = r.headers.get('location')
    print(url)
    if sys.version_info[:2] <= (2, 7):
        authorization_code = raw_input("\nAuthorization Code >>> ")
    else:
        authorization_code = input("\nAuthorization Code >>> ")
    return authorization_code


"""
Retrieving access_token and refresh_token from Token API.
"""


def retrieve_tokens(authorization_code):
    access_token_req = {
        "code": authorization_code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
        }
    content_length = len(urlencode(access_token_req))
    access_token_req['content-length'] = str(content_length)
    r = requests.post(base_url + "token", data=access_token_req)
    data = json.loads(r.text)
    return data


def get_refresh_token():
    access_token_req = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        }
    r = requests.post(base_url + "token", data=access_token_req)
    data = json.loads(r.text)
    return data


def main():
    authorization_code = retrieve_authorization_code()
    tokens = retrieve_tokens(authorization_code)
    refresh_token = tokens['refresh_token']
    print("Refresh Token:")
    print(refresh_token)


if __name__ == '__main__':
    main()
