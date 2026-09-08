@echo off
echo ============================================================
echo Verificando SmartFactory Web PILOTO
echo ============================================================
echo.

echo Backend principal:
curl http://127.0.0.1:8000/api/health
echo.
echo.

echo Servicio local de huella:
curl http://127.0.0.1:9001/api/huella/health
echo.
echo.

pause
