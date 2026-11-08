
@echo off
cd /d "%~dp0.."

echo ========================================
echo   EXPORTACION BASE DE DATOS SGE
echo ========================================
echo.
echo Exportando las 15 tablas del colegio...
echo.

python -X utf8 manage.py dumpdata ^
sistema.Rol ^
sistema.Usuario ^
sistema.Curso ^
sistema.Alumno ^
sistema.Asignatura ^
sistema.AsignaturaCurso ^
sistema.Evaluacion ^
sistema.Calificacion ^
sistema.RegistroAsistencia ^
sistema.EquipoTi ^
sistema.TicketSoporte ^
sistema.Insumo ^
sistema.SolicitudInsumo ^
sistema.DetalleInsumo ^
sistema.EventoCalendario ^
--indent 2 -o datos_iniciales.json

if errorlevel 1 (
    echo.
    echo ERROR al exportar la base de datos.
    pause
    exit /b 1
)

echo.
echo Exportacion completada correctamente.
echo Archivo generado: datos_iniciales.json
echo.
pause
