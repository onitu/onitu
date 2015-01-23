Flickr driver
=============

This is the Flickr driver for Onitu.

It allows you to synchronize a folder in Onitu with an album of your Flickr account.


Getting started
===============

First, you'll need to authorize Onitu to access to your Flickr files.

To do that, Flickr uses the OAuth authentication flow. It will provide you OAuth keys
proving that Onitu has the rights to handle the data on your account.

To retrieve those keys, run the get_tokens.py script provided with this driver.

The script will first ask you to access a webpage on Flickr to accept the Onitu application.

Then, after having accepted, Flickr redirects you on a page with a numerical code.
You need to copy this code and paste it back to the script, in your terminal.

If everything is OK, the script will then display the keys you'll be able to use in your Onitu configuration: the OAuth token and the OAuth token secret.

Use them in the Onitu setup.yml configuration file to make your driver able to communicate with Flickr.



Example
=======

Here is a sample example setup.yml configuration file that will synchronize the local folder `/home/baron_a/Pictures` with the Flickr album `test-onitu`:

```
name: example

folders:
  photos:
    mimetypes:
      - "image/*"

services:
  A:
    driver: local_storage 
    folders:
      photos: /home/baron_a/Pictures
  F:
   driver: flickr
   folders:
     photos: test-onitu
   options:
     oauth_token: YOUR_OAUTH_TOKEN
     oauth_token_secret: YOUR_OAUTH_TOKEN_SECRET
```

It may seem obvious, but please note the Flickr driver is made to transfer images. Don't try to make it upload any other type of data to Flickr, it won't work. 