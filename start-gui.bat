@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD=py -3"
where py >nul 2>nul
if errorlevel 1 set "PYTHON_CMD=python"

if not exist ".venv\Scripts\python.exe" (
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :error
)

call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error

call ".venv\Scripts\python.exe" -m pip install .
if errorlevel 1 goto :error

call ".venv\Scripts\python.exe" -m llm_sbom.cli gui
goto :eof

:error
echo Unable to start the GUI.
pause
exit /b 1
