
@echo off
cd /d "%~dp0.."

echo Exportando las 14 tablas del colegio...

python -X utf8 manage.py dumpdata sistema.Rol sistema.Usuario sistema.Curso sistema.Alumno sistema.Asignatura sistema.AsignaturaCurso sistema.Evaluacion sistema.Calificacion sistema.RegistroAsistencia sistema.EquipoTi sistema.TicketSoporte sistema.Insumo sistema.SolicitudInsumo sistema.DetalleInsumo --indent 2 -o datos_iniciales.json

if errorlevel 1 (
    echo ERROR al exportar la base de datos.
    pause
    exit /b 1
)

echo Exportacion completada correctamente.
pause
