from requests_oauthlib import OAuth1Session

if __name__ == '__main__':

    client_key = '66a1c393c8de67fbeef54bb785375e06'
    client_secret = '5bfbc7256872d085'

    base_url = 'https://www.flickr.com/services/oauth/'
    request_token_url = base_url + 'request_token'
    base_authorization_url = base_url + 'authorize'
    access_token_url = base_url + 'access_token'

    oauth_callback = 'https://api.flickr.com/services/rest/?method=flickr.test.echo&api_key=' + client_key

    oauth = OAuth1Session(client_key, client_secret=client_secret,
                          callback_uri=oauth_callback)
    fetch_response = oauth.fetch_request_token(request_token_url)

    request_token = fetch_response.get('oauth_token')
    token_secret = fetch_response.get('oauth_token_secret')

    # -------

    authorization_url = oauth.authorization_url(base_authorization_url,
                                                perms='delete')
    print 'Please go here and authorize onitu to access your account'
    print authorization_url
    redirect_response = raw_input('Paste here the full redirect URL: ')
    oauth_response = oauth.parse_authorization_response(redirect_response)

    verifier = oauth_response.get('oauth_verifier')

    # -------

    oauth = OAuth1Session(client_key,
                          client_secret=client_secret,
                          resource_owner_key=request_token,
                          resource_owner_secret=token_secret,
                          verifier=verifier)
    oauth_tokens = oauth.fetch_access_token(access_token_url)

    oauth_token = oauth_tokens.get('oauth_token')
    oauth_token_secret = oauth_tokens.get('oauth_token_secret')

    print '------------------------------------------------------'
    print 'yout oauth_token        = ' + oauth_token
    print 'yout oauth_token_secret = ' + oauth_token_secret
    print '------------------------------------------------------'
    print 'You can now paste these tokens in your setup.json file'
    print '------------------------------------------------------'
