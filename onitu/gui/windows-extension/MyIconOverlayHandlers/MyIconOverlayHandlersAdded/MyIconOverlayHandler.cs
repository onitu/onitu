using System;
using System.Runtime.InteropServices;
using Microsoft.Win32;
using System.IO;
using MyIconOverlayHandlers;
 
namespace MyIconOverlayHandlersAdded
{
    [ComVisible(true)]
    [Guid("9854f366-eb51-4189-84d0-1833400a6a09")]
    public class AMyIconOverlayHandlersAdded : MyIconOverlayHandlerBase
    {
        #region Class Properties
 
        protected override string OverlayIconFilePath
        {
            get
            {
                return Path.Combine(base.OverlayIconFilePath, @"AddedOverlay.ico");
            }
        }
 
        protected override string FileNameStart
        {
            get
            {
                return "added";
            }
        }
 
        #endregion Class Properties
    }
}