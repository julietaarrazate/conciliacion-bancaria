@echo off
REM Inicia backend + frontend web para desarrollo
REM Backend escucha en 0.0.0.0:8000 (accesible desde celular en misma WiFi)

echo.
echo === Conciliacion Bancaria - Modo Desarrollo ===
echo.

cd /d "%~dp0\backend"

echo [1/3] Mostrando IPs disponibles...
python network_info.py
echo.

echo [2/3] Iniciando backend en 0.0.0.0:8000 ...
start "Backend" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak > nul

echo [3/3] Iniciando frontend web en localhost:3000 ...
cd /d "%~dp0\frontend"
start "Frontend" cmd /k "npm run dev"

echo.
echo Listo! Dos ventanas se abrieron.
echo Backend Swagger:  http://localhost:8000/docs
echo Web:              http://localhost:3000
echo.
pause
