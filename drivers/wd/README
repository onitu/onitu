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
    driver: wd
    options:
        hostname: "https://dav.box.com"
        username: "me@mydomain.tld"
        password: "password"
        changes_timer: 360
    folders:
      backup: /dav/backup
```