To install this extension:

Copy the "OnituOverlayIcons" folder in "C:\ProgramData"

Load the solution in visual studio and compile it.

Open a command prompt with admin privileges.

Go to {Project Folder}\MyIconOverlayHandlersAdded\bin\Debug
	Register the assembly with the following command:
	C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe AMyIconOverlayHandlersAdded.dll /codebase


Go to {Project Folder}\MyIconOverlayHandlersPending\bin\Debug
	Register the assembly with the following command:
	C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe AMyIconOverlayHandlersPending.dll /codebase
	
Restart explorer.exe

Now (for this first version), if a file has "added" or "pending" in its name, an overlay icon is displayed.