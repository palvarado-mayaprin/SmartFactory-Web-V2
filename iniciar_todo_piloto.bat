@echo off
cd /d "%~dp0"

REM Abre backend principal y servicio de huella en dos ventanas separadas.
start "SmartFactory Backend 8000" cmd /k iniciar_backend_piloto.bat
start "SmartFactory Huella 9001" cmd /k iniciar_huella_local_piloto.bat

echo Se abrieron dos ventanas:
echo 1. Backend principal :8000
echo 2. Servicio local de huella :9001
echo.
echo Abra en navegador: http://127.0.0.1:8000
pause
