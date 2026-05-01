@echo off
setlocal

echo.
echo ================================================
echo  Conciliacion Bancaria - LOCAL
echo ================================================
echo.

cd /d "%~dp0"

REM Verificar que existen las carpetas
if not exist backend (
    echo ERROR: no se encuentra carpeta backend
    pause
    exit /b 1
)
if not exist frontend (
    echo ERROR: no se encuentra carpeta frontend
    pause
    exit /b 1
)

echo [1/4] Verificando Python...
where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en PATH
    pause
    exit /b 1
)
python --version

echo.
echo [2/4] Instalando deps backend (puede tardar 1-2 min la primera vez)...
cd backend
pip install -q -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install fallo
    pause
    exit /b 1
)

echo.
echo [3/4] Creando BD + usuarios admin/operador...
python seed.py
if errorlevel 1 (
    echo ERROR: seed.py fallo
    pause
    exit /b 1
)

echo.
echo Iniciando backend en ventana nueva...
start "Backend (no cerrar)" cmd /k "cd /d %~dp0backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

cd /d "%~dp0frontend"

if not exist node_modules (
    echo.
    echo [4/4] Instalando deps frontend (la primera vez tarda ~1 min)...
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install fallo
        pause
        exit /b 1
    )
) else (
    echo [4/4] Frontend ya tiene deps instaladas.
)

echo.
echo Iniciando frontend en ventana nueva...
start "Frontend Web (no cerrar)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Esperando 10 segundos a que arranquen los servidores...
timeout /t 10 /nobreak

echo.
echo Abriendo navegador...
start http://localhost:3000

echo.
echo ================================================
echo  TODO LISTO
echo ================================================
echo  Backend:   http://localhost:8000
echo  Swagger:   http://localhost:8000/docs
echo  Web:       http://localhost:3000
echo.
echo  Login:
echo    admin@caneland.com    / admin123
echo    operador@caneland.com / operador123
echo ================================================
echo.
echo  Si algo no anda, mira las 2 ventanas que se
echo  abrieron (Backend y Frontend Web) y mandame el error.
echo.
pause
