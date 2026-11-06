@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0sonar-scan.ps1" %*
exit /b %ERRORLEVEL%
