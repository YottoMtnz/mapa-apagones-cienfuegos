@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto fin
py -3 scraper\generar_sesion.py
:fin
pause
