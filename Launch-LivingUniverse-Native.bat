@echo off
setlocal
cd /d "%~dp0"
if not exist "LivingUniverse-Observer.exe" (
  echo The native Windows x64 observer is missing. Use Launch-LivingUniverse.bat instead.
  pause
  exit /b 1
)
echo Native observer: local read-only development utility, not the bare-metal kernel.
echo Copy the PRIVATE URL printed below into your browser. Keep this window open.
echo No administrator rights are needed. Ctrl+C stops the observer.
echo.
"%~dp0LivingUniverse-Observer.exe" --web "%~dp0LivingUniverse.html" %*
if errorlevel 1 (
  echo.
  echo Startup failed. Read the message above. The portable HTML remains available.
  pause
)
