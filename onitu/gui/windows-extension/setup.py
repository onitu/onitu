from distutils.core import setup
import py2exe, sys


try:
   import py2exe.mf as modulefinder
except ImportError:
   import modulefinder
import win32com
for p in win32com.__path__[1:]:
    modulefinder.AddPackagePath("win32com", p)
for extra in ["win32com.shell"]:
   __import__(extra)
   m = sys.modules[extra]
   for p in m.__path__[1:]:
       modulefinder.AddPackagePath(extra, p)

class Target:
    def __init__(self, **kw):
        self.__dict__.update(kw)
        # for the version info resources (Properties -- Version)
        self.version = "1.0"
        self.company_name = "Onitu"
        self.copyright = "MIT License"
        self.name = "Onitu Icon Overlay"

onitu_target = Target(
    description = "Onitu Icon Overlay Windows Extension",
    # use module name for win32com exe/dll server
    modules = ["OnituIconOverlay"],
    # specify which type of com server you want (exe and/or dll)
    create_exe = False,
    create_dll = True
    )

setup(
    version = "1.0",
    zipfile=None,
    description = "Onitu Icon Overlay Windows Extension",
    name = "Onitu Icon Overlay",
    author="Onitu",
    com_server = [onitu_target],
    )