@echo off
cd /d "%~dp0"
set DEBUG=false
"%~dp0integration-staging\python\python.exe" "%~dp0run_server.py"
pause
