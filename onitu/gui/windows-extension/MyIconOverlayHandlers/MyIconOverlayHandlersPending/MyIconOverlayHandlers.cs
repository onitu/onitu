using System;
using System.Runtime.InteropServices;
using Microsoft.Win32;
using System.IO;
using MyIconOverlayHandlers;

namespace MyIconOverlayHandlersPending
{
    [ComVisible(true)]
    [Guid("4e4b5be0-8a16-4768-83af-2bf0c139cfbc")]
    public class AMyIconOverlayHandlersPending : MyIconOverlayHandlerBase
    {
        #region Class Properties

        protected override string OverlayIconFilePath
        {
            get
            {
                return Path.Combine(base.OverlayIconFilePath, @"PendingOverlay.ico");
            }
        }

        protected override string FileStatus
        {
            get
            {
                return "pending";
            }
        }

        #endregion Class Properties
    }
}