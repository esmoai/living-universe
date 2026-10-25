@echo off
setlocal
if not exist "%~dp0LivingUniverse.html" (
  echo LivingUniverse.html is missing. Extract the complete ZIP first.
  pause
  exit /b 1
)
start "" "%~dp0LivingUniverse.html"
