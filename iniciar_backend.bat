@echo off
setlocal

cd /d "%~dp0"

if not exist venv (
    echo No se encontro el entorno virtual. Ejecuta primero instalar_dependencias.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Iniciando backend Offix en http://localhost:8000
echo Documentacion OpenAPI/Swagger en http://localhost:8000/docs
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
