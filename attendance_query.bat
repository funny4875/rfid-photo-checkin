@echo off
cd /d "%~dp0"
python client\attendance_query.py
if errorlevel 1 pause
