@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\check_update.ps1" -RepoRoot "%~dp0"
if errorlevel 10 exit /b 0
cd /d "%~dp0server"
echo Checking Python packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install backend packages.
  pause
  exit /b 1
)
echo Starting RFID backend server GUI...
python server_gui.py
pause
endlocal
