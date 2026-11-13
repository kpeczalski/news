Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
sh.Environment("Process")("PF_HIDDEN") = "1"
sh.Run "cmd /c """ & dir & "\start.bat""", 0, False
