@echo off
setlocal
cd /d "%~dp0"
py -3.11 -c "import sys" >nul 2>&1
if errorlevel 1 (
  py -3 tools/bootstrap.py
) else (
  py -3.11 tools/bootstrap.py
)
if errorlevel 1 exit /b 1
echo Xputty Open Weight is ready. Run START-WINDOWS.cmd.
