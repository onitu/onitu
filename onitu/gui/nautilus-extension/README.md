To enable this extension:

Install 'python-nautilus' package
Copy 'onitu-nautilus.py' in '~/.local/share/nautilus-python/extensions'. You may nneed to create this folder.
Reload nautilus: nautilus -q; nautilus


If when you launch Nautilus you've got these errors:

Nautilus-Python-WARNING **: pygobject initialization failed
Nautilus-Python-WARNING **: nautilus_python_init_python failed

Try, to reinstall nautilus (for example:)

killall nautilus
sudo apt-get remove --purge nautilus
sudo apt-get update
sudo apt-get install nautilus
