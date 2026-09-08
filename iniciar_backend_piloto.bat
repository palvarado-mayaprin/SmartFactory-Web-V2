@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM SmartFactory Web - Backend principal PILOTO
REM Puerto: 8000
REM ============================================================

set SMARTFACTORY_ENABLE_REAL_DB_WRITES=1
set SMARTFACTORY_ENABLE_REAL_MQTT_DB_WRITES=1
set SMARTFACTORY_ENABLE_REAL_MQTT_PUBLISH=1

set SMARTFACTORY_BACKEND_HOST=127.0.0.1
set SMARTFACTORY_BACKEND_PORT=8000

if not exist "venv\Scripts\activate.bat" (
    echo No se encontro venv\Scripts\activate.bat
    echo Cree el entorno virtual o ejecute desde la carpeta correcta.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

if not exist logs mkdir logs

echo ============================================================
echo Iniciando SmartFactory Backend Principal
echo URL: http://127.0.0.1:8000
echo ============================================================

uvicorn main:app --host 127.0.0.1 --port 8000

pause
