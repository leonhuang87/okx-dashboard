Set objShell = CreateObject("WScript.Shell")

' Check if server is already running
Set objHTTP = CreateObject("MSXML2.XMLHTTP")
On Error Resume Next
objHTTP.Open "GET", "http://localhost:5000/api/status", False
objHTTP.Send
If Err.Number = 0 And objHTTP.Status = 200 Then
    objShell.Run "http://localhost:5000"
    WScript.Quit
End If
On Error GoTo 0

' Get script directory
strDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)

' Start server silently
objShell.CurrentDirectory = strDir
objShell.Run "pythonw -B server.py", 0, False

' Wait for server to be ready (max 15 seconds)
For i = 1 To 30
    WScript.Sleep 500
    On Error Resume Next
    Set objHTTP2 = CreateObject("MSXML2.XMLHTTP")
    objHTTP2.Open "GET", "http://localhost:5000/api/status", False
    objHTTP2.Send
    If Err.Number = 0 And objHTTP2.Status = 200 Then
        objShell.Run "http://localhost:5000"
        WScript.Quit
    End If
    On Error GoTo 0
Next

MsgBox "Server startup timeout. Check Python or port 5000.", vbExclamation, "OKX Trading"
