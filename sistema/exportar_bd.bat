@echo off
echo Exportando las 13 tablas del colegio a datos_iniciales.json...
python -X utf8 manage.py dumpdata sistema.Rol sistema.Usuario sistema.Curso sistema.Alumno sistema.Asignatura sistema.AsignaturaCurso sistema.Calificacion sistema.RegistroAsistencia sistema.EquipoTi sistema.TicketSoporte sistema.Insumo sistema.SolicitudInsumo sistema.DetalleInsumo --indent 2 -o datos_iniciales.json
echo ¡Listo! Ya puedes hacer git add, commit y push.