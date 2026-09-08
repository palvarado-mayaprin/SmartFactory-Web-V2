@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM SmartFactory Web - Servicio local de huella PILOTO
REM Puerto: 9001
REM Se comunica con EnrollmentSample CS.exe por socket 127.0.0.1:8888
REM ============================================================

set SMARTFACTORY_HUELLA_MODO=REAL
set SMARTFACTORY_HUELLA_HOST=127.0.0.1
set SMARTFACTORY_HUELLA_PORT=8888
set SMARTFACTORY_HUELLA_COMANDO=enrollFingerPrint
set SMARTFACTORY_HUELLA_REINICIAR_EXE_ANTES_LECTURA=1
set SMARTFACTORY_HUELLA_TIMEOUT_SEGUNDOS=30

if not exist "venv\Scripts\activate.bat" (
    echo No se encontro venv\Scripts\activate.bat
    echo Cree el entorno virtual o ejecute desde la carpeta correcta.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

if not exist logs mkdir logs

echo ============================================================
echo Iniciando SmartFactory Huella Local
echo URL: http://127.0.0.1:9001/api/huella/health
echo ============================================================

uvicorn huella_local.main:app --host 127.0.0.1 --port 9001

pause
