Set WshShell = CreateObject("WScript.Shell")
botPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "cmd /c cd /d """ & botPath & """ && """ & botPath & "\.venv\Scripts\python.exe"" -u feishu_bot.py > bot_output.log 2>&1", 0
