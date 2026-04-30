@echo off
REM Inicia Expo dev server para la app movil

cd /d "%~dp0\mobile"

echo.
echo === Iniciando app movil (Expo) ===
echo.
echo Cuando aparezca el QR:
echo   1. Abri Expo Go en el celular (instalar de la Play Store si no lo tenes)
echo   2. Escanea el QR
echo   3. La app abrira en el celular
echo.
echo IMPORTANTE: el celular tiene que estar en la misma WiFi que esta PC.
echo.

call npm install
npx expo start --tunnel

pause
