import win32traceutil

from win32com.shell import shell, shellcon
import pythoncom
import winerror
import os

REG_PATH = r'Software\Microsoft\Windows\CurrentVersion\Explorer\ShellIconOverlayIdentifiers\OnituIconOverlay'

class OnituIconOverlay:
    _reg_clsid_= '{7160C572-84FC-42A7-B541-6A48C009AF05}'

    _reg_progid_= 'Onitu.IconOverlayHandler'
    _reg_desc_= 'Icon Overlay Handler for Onitu'
    _public_methods_ = ['GetOverlayInfo','GetPriority','IsMemberOf']
    _com_interfaces_=[shell.IID_IShellIconOverlayIdentifier, pythoncom.IID_IDispatch]

    def __init__(self):
        pass

    def GetOverlayInfo(self):
        return (os.path.abspath(r'icons\added.ico'), 0, shellcon.ISIOI_ICONFILE)

    def GetPriority(self):
        return 0

    def IsMemberOf(self, fname, attributes):
        print('ismemberOf', fname, os.path.basename(fname))
        if os.path.basename(fname) == "onitu":
            return winerror.S_OK
        return winerror.E_FAIL

def DllRegisterServer():
    print "Registering %s" % REG_PATH
    import _winreg
    key = _winreg.CreateKey(_winreg.HKEY_LOCAL_MACHINE, REG_PATH)
    subkey = _winreg.CreateKey(key, OnituIconOverlay._reg_progid_)
    _winreg.SetValueEx(subkey, None, 0, _winreg.REG_SZ, OnituIconOverlay._reg_clsid_)
    print "Registration complete: %s" % OnituIconOverlay._reg_desc_

def DllUnregisterServer():
    print "Unregistering %s" % REG_PATH
    import _winreg
    try:
        key = _winreg.DeleteKey(_winreg.HKEY_LOCAL_MACHINE, r"%s\%s" % (REG_PATH, OnituIconOverlay._reg_progid_))
    except WindowsError, details:
        import errno
        if details.errno != errno.ENOENT:
            raise
    print "Unregistration complete: %s" % OnituIconOverlay._reg_desc_

if __name__=='__main__':
    from win32com.server import register
    print (OnituIconOverlay._reg_clsid_)
    register.UseCommandLine(OnituIconOverlay,
                            finalize_register = DllRegisterServer,
                            finalize_unregister = DllUnregisterServer)