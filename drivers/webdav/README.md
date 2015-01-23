Getting started with the Webdav driver
======================================

The driver handles the following options:

- hostname (no default value)
- username (default value is "")
- password (default value is "")
- changes_timer (default value is 60)

An example of setup.yml which can be used to store files on [box](http://box.com)

```
name: example

folders:
  docs:
    file_size:
      max: 2G

services:
  A:
    driver: local_storage
    folders:
      docs: ~/Documents
  B:
    driver: webdav
    options:
        hostname: "https://dav.box.com"
        username: "me@mydomain.tld"
        password: "password"
        changes_timer: 360
    folders:
      backup: /dav/backup
```

To test the driver, you can define the following env var:

- ONITU_WEBDAV_HOSTNAME
- ONITU_WEBDAV_CHANGE_TIMER
- ONITU_WEBDAV_USERNAME
- ONITU_WEBDAV_PASSWORD
- ONITU_WEBDAV_ROOT to define where the files will be stored during the tests.

To launch the tests:

```
ONITU_TEST_TIME_UNIT=5 ONITU_TEST_DRIVER=webdav py.test tests/
```
