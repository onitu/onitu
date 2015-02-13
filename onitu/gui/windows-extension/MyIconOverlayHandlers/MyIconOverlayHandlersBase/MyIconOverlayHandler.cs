

using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

using System.Runtime.InteropServices;
using Microsoft.Win32;
using System.IO;

using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace MyIconOverlayHandlers
{
    [Flags]
    public enum HFLAGS : uint
    {
        ISIOI_ICONFILE = 0x00000001,
        ISIOI_ICONINDEX = 0x00000002
    }

    [Flags]
    public enum HRESULT : uint
    {
        S_OK = 0x00000000,
        S_FALSE = 0x00000001,
        E_ABORT = 0x80004004,
        E_ACCESSDENIED = 0x80070005,
        E_FAIL = 0x80004005,
        E_HANDLE = 0x80070006,
        E_INVALIDARG = 0x80070057,
        E_NOINTERFACE = 0x80004002,
        E_OUTOFMEMORY = 0x8007000E,
        E_POINTER = 0x80004003,
        E_UNEXPECTED = 0x8000FFFF
    }

    public enum PFSTATUS
    {
        SYNCING,
        OK,
        LOCKED,
        UNLOCKED,
        CLOUD,
        SHORTCUT,
        NULL
    }


    public sealed class ShellInterop
    {
        private ShellInterop()
        {
        }

        [DllImport("shell32.dll")]
        public static extern void SHChangeNotify(int eventID, uint flags, IntPtr item1, IntPtr item2);
    }


    [ComVisible(false)]
    [ComImport]
    [Guid("0C6C4200-C589-11D0-999A-00C04FD655E1")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IShellIconOverlayIdentifier
    {
        [PreserveSig]
        int IsMemberOf([MarshalAs(UnmanagedType.LPWStr)]string path, uint attributes);

        [PreserveSig]
        int GetOverlayInfo(IntPtr iconFileBuffer, int iconFileBufferSize, out int iconIndex, out uint flags);

        [PreserveSig]
        int GetPriority(out int priority);
    }
    
    [ComVisible(false)]
    [Guid("1c19406f-797b-42dd-8912-9a55c752ec44")]
    public class MyIconOverlayHandlerBase : IShellIconOverlayIdentifier
    {
        #region Class Properties

        protected virtual string OverlayIconFilePath
        {
            get
            {
                return Path.Combine(
                     new string[] { Path.GetPathRoot(Environment.SystemDirectory),
                             "ProgramData",
                             "OnituOverlayIcons" }).ToLowerInvariant();
            }
        }

        protected virtual int Priority
        {
            get
            {
                return 0;  // 0-100 (0 is highest priority)
            }
        }

        protected virtual string FileStatus
        {
            get
            {
                return string.Empty;
            }
        }

        #endregion Class Properties



        #region IShellIconOverlayIdentifier Members

        public int IsMemberOf(string path, uint attributes)
        {
            try
            {
                unchecked
                {
                    string tmp_files = System.IO.Path.GetTempPath() + "onitu_synced_files";
                    string fileName = Path.GetFileName(path);

                    using (StreamReader r = new StreamReader(tmp_files))
                    {
                        string json = r.ReadToEnd();
                        json = json.Replace("\\", "\\\\");
                        JObject jsonVal = JObject.Parse(json) as JObject;

                        IList<string> fileList = jsonVal.Properties().Select(p => p.Name).ToList();
                     
                        foreach (string file in fileList)
                        {
                            if (path == file)
                            {
                                string status = (string)jsonVal.GetValue(file);
                                if (status == FileStatus)
                                {
                                    return (int)HRESULT.S_OK;
                                }
                            }
                        }
                        return (int)HRESULT.S_FALSE;
                    }
                }
            }
            catch
            {
                unchecked
                {
                    return (int)HRESULT.E_FAIL;
                }
            }
        }

        public int GetOverlayInfo(IntPtr iconFileBuffer, int iconFileBufferSize, out int iconIndex, out uint flags)
        {
            string fname = OverlayIconFilePath;

            int bytesCount = System.Text.Encoding.Unicode.GetByteCount(fname);

            byte[] bytes = System.Text.Encoding.Unicode.GetBytes(fname);

            if (bytes.Length + 2 < iconFileBufferSize)
            {
                for (int i = 0; i < bytes.Length; i++)
                {
                    Marshal.WriteByte(iconFileBuffer, i, bytes[i]);
                }
                //write the "\0\0"
                Marshal.WriteByte(iconFileBuffer, bytes.Length, 0);
                Marshal.WriteByte(iconFileBuffer, bytes.Length + 1, 0);
            }

            iconIndex = 0;
            flags = (int)(HFLAGS.ISIOI_ICONFILE | HFLAGS.ISIOI_ICONINDEX);
            return (int)HRESULT.S_OK;
        }

        public int GetPriority(out int priority)
        {
            priority = Priority;
            return (int)HRESULT.S_OK;
        }

        #endregion IShellIconOverlayIdentifier Members


        #region Registry

        [ComRegisterFunction]
        public static void Register(Type t)
        {
            RegistryKey rk = Registry.LocalMachine.CreateSubKey
(@"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\ShellIconOverlayIdentifiers\" + t.Name);
            rk.SetValue(string.Empty, t.GUID.ToString("B").ToUpper());
            rk.Close();
            ShellInterop.SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero);
        }

        [ComUnregisterFunction]
        public static void Unregister(Type t)
        {
            Registry.LocalMachine.DeleteSubKeyTree(
@"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\ShellIconOverlayIdentifiers\" + t.Name);
            ShellInterop.SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero);
        }

        #endregion Registry

    }
}
