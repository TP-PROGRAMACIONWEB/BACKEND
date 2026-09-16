@echo off
setlocal

cd /d "%~dp0"

if not exist venv (
    echo No se encontro el entorno virtual. Ejecuta primero instalar_dependencias.bat
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo Aplicando migraciones pendientes a la base configurada en DATABASE_URL (.env)...
echo Solo aplica a PostgreSQL: la base SQLite local se crea sola.
alembic upgrade head

pause
