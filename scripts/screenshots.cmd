@echo off
chcp 65001 >nul
setlocal
set "ROOT=%~dp0.."
set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%ROOT%\scripts\epic.py" screenshots %*
exit /b %ERRORLEVEL%
