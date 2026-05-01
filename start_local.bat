@echo off
REM Inicia TODO en local (sin necesidad de Render/Vercel)

echo.
echo ===================================================
echo  Conciliacion Bancaria - Modo LOCAL (sin nube)
echo ===================================================
echo.

cd /d "%~dp0\backend"

echo [1/3] Instalando dependencias backend si hacen falta...
pip install -q -r requirements.txt

echo.
echo [2/3] Creando BD local + usuarios admin/operador...
python seed.py

echo.
echo [3/3] Mostrando IPs disponibles para acceso movil...
python network_info.py

echo.
echo ===================================================
echo Iniciando backend en http://localhost:8000
echo Iniciando web en    http://localhost:3000
echo ===================================================
echo.

start "Backend" cmd /k "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak > nul

cd /d "%~dp0\frontend"
if not exist node_modules (
    echo Instalando dependencias web...
    call npm install
)
start "Frontend Web" cmd /k "npm run dev"

timeout /t 5 /nobreak > nul

echo.
echo Abriendo navegador...
start http://localhost:3000

echo.
echo Login con:
echo   admin@caneland.com / admin123
echo   operador@caneland.com / operador123
echo.
pause
