@echo off
setlocal
cd /d "%~dp0"
set "LOG=%~dp0xpano_gui_error.log"
set "QTWEBENGINE_DISABLE_SANDBOX=1"
set "PYTHONNOUSERSITE=1"

if exist "%LOG%" del "%LOG%"

if exist "%~dp0.venv-release\Scripts\python.exe" (
    set "XPANO_PY=%~dp0.venv-release\Scripts\python.exe"
) else if exist "%~dp0.venv\Scripts\python.exe" (
    set "XPANO_PY=%~dp0.venv\Scripts\python.exe"
) else (
    set "XPANO_PY=python.exe"
)

echo Starting xPano Workbench...
"%XPANO_PY%" -m xpano_workbench >> "%LOG%" 2>&1

if errorlevel 1 (
    echo.
    echo xPano failed. Error log:
    echo %LOG%
    echo.
    type "%LOG%"
) else (
    echo xPano closed normally.
)

pause
