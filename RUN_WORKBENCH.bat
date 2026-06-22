@echo off
setlocal
cd /d "%~dp0"

set "QTWEBENGINE_DISABLE_SANDBOX=1"
set "PYTHONNOUSERSITE=1"

if exist "%~dp0.venv-release\Scripts\pythonw.exe" (
    set "XPANO_PY=%~dp0.venv-release\Scripts\pythonw.exe"
) else if exist "%~dp0.venv\Scripts\pythonw.exe" (
    set "XPANO_PY=%~dp0.venv\Scripts\pythonw.exe"
) else if exist "%~dp0.venv-release\Scripts\python.exe" (
    set "XPANO_PY=%~dp0.venv-release\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "XPANO_PY=%~dp0.venv\Scripts\python.exe"
) else (
    set "XPANO_PY=pythonw.exe"
)

start "" "%XPANO_PY%" -m xpano_workbench
