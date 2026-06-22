Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
venvRelease = fso.BuildPath(baseDir, ".venv-release\Scripts\pythonw.exe")
venvLocal = fso.BuildPath(baseDir, ".venv\Scripts\pythonw.exe")

shell.CurrentDirectory = baseDir
shell.Environment("PROCESS")("QTWEBENGINE_DISABLE_SANDBOX") = "1"
shell.Environment("PROCESS")("PYTHONNOUSERSITE") = "1"

If fso.FileExists(venvRelease) Then
    shell.Run """" & venvRelease & """ -m xpano_workbench", 0, False
ElseIf fso.FileExists(venvLocal) Then
    shell.Run """" & venvLocal & """ -m xpano_workbench", 0, False
Else
    shell.Run "pythonw.exe -m xpano_workbench", 0, False
End If
