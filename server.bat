@echo off
chcp 65001 >nul
cd /d "%~dp0server"
echo Checking Python packages...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install backend packages.
  pause
  exit /b 1
)
echo Starting RFID backend server on http://0.0.0.0:5000
python app.py
pause
