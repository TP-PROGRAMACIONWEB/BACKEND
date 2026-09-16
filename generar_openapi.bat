@echo off
setlocal

cd /d "%~dp0"

if not exist venv (
    echo No se encontro el entorno virtual. Ejecuta primero instalar_dependencias.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Generando docs\openapi.json a partir del codigo actual...
python -m app.scripts.export_openapi

pause
