@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe call INSTALL-WINDOWS.cmd
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -u -X utf8 launch.py
pause
