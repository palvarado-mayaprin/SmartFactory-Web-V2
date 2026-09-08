@echo off
REM Ejecutar desde la carpeta src_web con el venv activo.
REM Servicio local de huella simulado en http://127.0.0.1:9001
uvicorn huella_local.main:app --host 127.0.0.1 --port 9001 --reload
pause
