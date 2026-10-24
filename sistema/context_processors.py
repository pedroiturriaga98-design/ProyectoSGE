
from .models import Alumno


def estudiantes_apoderado(request):
    contexto = {
        'apoderado_alumnos': [],
        'apoderado_alumno_actual': None,
    }

    if request.session.get('rol_id') != 3:
        return contexto

    rut_apoderado = request.session.get('usuario_rut')

    if not rut_apoderado:
        return contexto

    alumnos = list(
        Alumno.objects.filter(
            usuario_rut_id=rut_apoderado
        )
        .select_related('curso_id_curso')
        .order_by('nombre_completo')
    )

    contexto['apoderado_alumnos'] = alumnos

    rut_solicitado = request.GET.get('alumno', '').strip()

    if rut_solicitado:
        seleccionado = next(
            (
                alumno for alumno in alumnos
                if alumno.rut_alumno == rut_solicitado
            ),
            None
        )

        # No seleccionar alumnos que no pertenezcan al apoderado.
        contexto['apoderado_alumno_actual'] = seleccionado
    elif alumnos:
        contexto['apoderado_alumno_actual'] = alumnos[0]

    return contexto
