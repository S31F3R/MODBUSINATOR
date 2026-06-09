@echo off
cd /d "%~dp0"

set CMD=.\.venv\Scripts\python.exe .\modbusDUMPER.py --connection TCP --host 127.0.0.1 --port 5020 --register IR --numParams 24

cmd.exe /k "%CMD% & doskey dump=%CMD%"