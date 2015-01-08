import os.path
import tempfile
import json
import path
import urllib2

from gi.repository import Nautilus, GObject

class OnituIconOverlayExtension(GObject.GObject, Nautilus.InfoProvider):
    def __init__(self):
        pass

    def update_file_info(self, file):

        tmp_dir = tempfile.gettempdir()
        tmp_filename = tmp_dir + '/onitu_synced_files'

        try:
            with open(tmp_filename, "r") as jsonFile:
                data = json.load(jsonFile)
        except IOError as e:
            data = dict()

        file_path = urllib2.unquote(file.get_uri()[7:])
        status = data.get(file_path)

        if status == "pending":
            file.add_emblem("onitu_pending")
        elif status == "synced":
            file.add_emblem("onitu_sync")
