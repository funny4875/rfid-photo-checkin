@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0client" || (
  echo Cannot find client folder.
  pause
  exit /b 1
)

set "PYTHON_EXE="
for /f "delims=" %%P in ('where python 2^>nul') do (
  if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
  echo Cannot find python. Please install Python or check PATH.
  pause
  exit /b 1
)

echo Using Python: !PYTHON_EXE!
"!PYTHON_EXE!" -c "import client_ui" >nul 2>nul
if errorlevel 1 (
  echo Failed to import client_ui.py.
  "!PYTHON_EXE!" -c "import client_ui"
  pause
  exit /b 1
)

"!PYTHON_EXE!" "%CD%\client_ui.py"

endlocal
