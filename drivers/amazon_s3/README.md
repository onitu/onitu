Amazon S3 Driver
================

This is the Onitu driver for the Amazon S3 cloud service. It permits to sync Onitu with a S3 bucket.

Important Note: Please keep in mind this driver uses authenticated interaction (using your Amazon credentials) with the Amazon S3 REST API.
	  As it uses your AWS Account, you'll be charged accordingly for every interaction with a S3 bucket through Onitu. You have full responsability
	  for transfers you are getting charged for on your bucket when using Onitu. If you still want to try Onitu, Amazon proposes a Free Tier offer
	  including 20,000 Get Requests and 2,000 Put Requests on Amazon S3 (see http://aws.amazon.com/free/).

To make it work you're going to need your Amazon Access ID and your Amazon Secret Access Key.

If you already have an AWS account, you can retrieve them at https://console.aws.amazon.com/iam/home?#security_credential, tab "Access Keys (Access Key ID and Secret Access Key)".

Once you have them, you need to create a new driver service called "amazon_s3" in the setup YAML file (setup.yml), and fill in the following options fields:
  - bucket: the name of the bucket you want to use with Onitu
  - aws_access_key: Put here your AWS Access Key
  - aws_secret_key: Put here your AWS Secret Key
  - changes_timer: Onitu periodically checks for changes on the bucket. Use this to set a period of time, in seconds, between each retry. Defaults to 10 seconds if you omit it

Here is a sample configuration to synchronize a local folder and a folder on your Amazon S3:

"
name: example

folders:
  music:
    mimetypes:
      - "audio/*"
  docs:
    blacklist:
      - "*.bak" 
      - Private/
  backup:
    blacklist:
      - ".*"
    file_size:
      max: 2G

services:
  A:
    driver: local_storage 
    folders:
      music: /home/baron_a/Music
      docs: /home/baron_a/Docs
  S:  
    driver: amazon_s3
    folders:
       music: pando/music/
    options:
        bucket: onitu-test-2
        aws_access_key: AKIAJSWLJPXBXENIPIZQ
        aws_secret_key: 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
        changes_timer : 10
"