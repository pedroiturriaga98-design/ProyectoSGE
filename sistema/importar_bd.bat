
@echo off
cd /d "%~dp0.."

echo ========================================
echo   IMPORTACION BASE DE DATOS SGE
echo ========================================
echo.
echo Cargando datos en MySQL local...
echo.

if not exist "datos_iniciales.json" (
    echo ERROR: No existe datos_iniciales.json
    pause
    exit /b 1
)

python -X utf8 manage.py loaddata datos_iniciales.json

if errorlevel 1 (
    echo.
    echo ERROR al importar la base de datos.
    echo Revisa el mensaje anterior.
    pause
    exit /b 1
)

echo.
echo Base de datos actualizada correctamente.
echo.
pause
