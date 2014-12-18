import os.path
from gi.repository import Nautilus, GObject

class OnituIconOverlayExtension(GObject.GObject, Nautilus.InfoProvider):
    def __init__(self):
        pass

    def update_file_info(self, file):
        if os.path.splitext(file.get_name())[1] == ".onitu":
            file.add_emblem("multimedia")
        elif (file.get_string_attribute("onitu_local_storage") != ""):
            file.add_emblem("onitu")
