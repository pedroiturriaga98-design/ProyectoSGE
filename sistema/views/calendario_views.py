import json
import logging
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, Http404
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from sistema.models import Alumno, AsignaturaCurso, Curso, EventoCalendario
from .auth_views import require_role

logger_calendario = logging.getLogger(__name__)

COLORES_CALENDARIO = {
    "evaluacion": "#2563eb",
    "reunion": "#f97316",
    "extracurricular": "#8b5cf6",
    "colegio": "#16a34a",
    "feriado": "#dc2626",
}


def _cal_error(mensaje, status=400):
    return JsonResponse({"ok": False, "error": mensaje}, status=status)


def _cal_fecha(valor):
    fecha = parse_datetime(str(valor or ""))
    if fecha is None:
        raise ValueError("Fecha u hora inválida.")
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(
            fecha, timezone.get_current_timezone()
        )
    return fecha


def _cal_serializar(evento):
    return {
        "id": str(evento.id_evento),
        "title": evento.titulo,
        "start": evento.fecha_inicio.isoformat(),
        "end": evento.fecha_fin.isoformat(),
        "backgroundColor": COLORES_CALENDARIO.get(
            evento.tipo_evento, "#64748b"
        ),
        "borderColor": COLORES_CALENDARIO.get(
            evento.tipo_evento, "#64748b"
        ),
        "extendedProps": {
            "descripcion": evento.descripcion or "",
            "lugar": evento.lugar or "",
            "tipo": evento.tipo_evento,
            "alcance": evento.alcance,
            "id_asig_curso": evento.id_asig_curso_id,
            "id_curso": evento.id_curso_id,
            "creador": evento.usuario_rut_id,
        }
    }


def _cal_rango(request):
    inicio = _cal_fecha(request.GET.get("start"))
    fin = _cal_fecha(request.GET.get("end"))

    if fin <= inicio or fin - inicio > timedelta(days=400):
        raise ValueError("Rango de fechas inválido.")

    return inicio, fin


def _cal_eventos_rango(inicio, fin):
    return EventoCalendario.objects.filter(
        fecha_inicio__lt=fin,
        fecha_fin__gt=inicio
    ).order_by("fecha_inicio")


def _cal_asignaciones_profesor(request):
    rut = request.session.get("usuario_rut")
    return AsignaturaCurso.objects.filter(
        usuario_rut_id=rut
    ).select_related(
        "curso_id_curso", "asignatura_id_asignatura"
    ).order_by(
        "curso_id_curso__nombre_curso",
        "asignatura_id_asignatura__nombre_asignatura"
    )


@require_role([2])
def profesor_calendario(request):
    rut_profesor = request.session.get("usuario_rut")

    asignaciones = list(_cal_asignaciones_profesor(request))

    opciones = [
        {
            "id": a.id_asig_curso,
            "curso_id": a.curso_id_curso_id,
            "nombre": (
                f"{a.asignatura_id_asignatura.nombre_asignatura} "
                f"— {a.curso_id_curso.nombre_curso}"
            )
        }
        for a in asignaciones
    ]

    jefaturas = (
        Curso.objects
        .filter(usuario_rut_id=rut_profesor)
        .order_by("nombre_curso")
    )

    cursos = [
        {
            "id": curso.id_curso,
            "nombre": curso.nombre_curso
        }
        for curso in jefaturas
    ]

    return render(request, "profesor_calendario.html", {
        "asignaciones": opciones,
        "cursos": cursos,
    })


@require_role([2])
@require_GET
def profesor_calendario_eventos(request):
    try:
        inicio, fin = _cal_rango(request)
        eventos = _cal_eventos_rango(inicio, fin)
        return JsonResponse(
            [_cal_serializar(e) for e in eventos],
            safe=False
        )
    except ValueError as exc:
        return _cal_error(str(exc))
    except Exception:
        logger_calendario.exception(
            "Error al consultar calendario profesor"
        )
        return _cal_error(
            "No se pudieron consultar los eventos.", 500
        )


@require_role([3])
def apoderado_calendario(request):
    rut_apoderado = request.session.get("usuario_rut")

    alumnos = list(
        Alumno.objects
        .filter(usuario_rut_id=rut_apoderado)
        .select_related("curso_id_curso")
        .order_by("nombre_completo")
    )

    rut_solicitado = request.GET.get("alumno", "").strip()

    if rut_solicitado:
        alumno_seleccionado = next(
            (
                alumno for alumno in alumnos
                if alumno.rut_alumno == rut_solicitado
            ),
            None
        )

        if alumno_seleccionado is None:
            raise Http404(
                "Estudiante no asociado a este apoderado."
            )
    else:
        alumno_seleccionado = alumnos[0] if alumnos else None

    estudiantes = [
        {
            "rut": alumno.rut_alumno,
            "nombre": alumno.nombre_completo,
            "curso": alumno.curso_id_curso.nombre_curso,
        }
        for alumno in alumnos
    ]

    return render(request, "apoderado_calendario.html", {
        "estudiantes": estudiantes,
        "alumnos": alumnos,
        "alumno_seleccionado": alumno_seleccionado,
        "rut_alumno_seleccionado": (
            alumno_seleccionado.rut_alumno
            if alumno_seleccionado else ""
        ),
    })


@require_role([3])
@require_GET
def apoderado_calendario_eventos(request):
    rut_apoderado = request.session.get("usuario_rut")
    rut_alumno = request.GET.get("alumno", "").strip()

    if not rut_alumno:
        return _cal_error("Selecciona un estudiante.")

    alumno = Alumno.objects.filter(
        rut_alumno=rut_alumno,
        usuario_rut_id=rut_apoderado
    ).first()

    if alumno is None:
        return _cal_error(
            "Estudiante no autorizado.", 403
        )

    try:
        inicio, fin = _cal_rango(request)
        curso_id = alumno.curso_id_curso_id

        asignaciones = AsignaturaCurso.objects.filter(
            curso_id_curso_id=curso_id
        ).values_list("id_asig_curso", flat=True)

        eventos = _cal_eventos_rango(inicio, fin).filter(
            Q(alcance="general")
            | Q(alcance="curso", id_curso_id=curso_id)
            | Q(
                alcance="asignatura",
                id_asig_curso_id__in=asignaciones
            )
        )

        return JsonResponse(
            [_cal_serializar(e) for e in eventos],
            safe=False
        )

    except ValueError as exc:
        return _cal_error(str(exc))
    except Exception:
        logger_calendario.exception(
            "Error al consultar calendario apoderado"
        )
        return _cal_error(
            "No se pudieron consultar los eventos.", 500
        )


@require_role([2])
@require_POST
def profesor_calendario_guardar(request):
    rut_profesor = request.session.get("usuario_rut")

    if not rut_profesor:
        return _cal_error("Sesión no válida.", 403)

    try:
        datos = json.loads(request.body)
        if not isinstance(datos, dict):
            return _cal_error("Solicitud inválida.")

        titulo = str(datos.get("titulo") or "").strip()
        descripcion = str(datos.get("descripcion") or "").strip()
        lugar = str(datos.get("lugar") or "").strip()
        tipo = str(datos.get("tipo_evento") or "").strip()
        alcance = str(datos.get("alcance") or "").strip()

        inicio = _cal_fecha(datos.get("fecha_inicio"))
        fin = _cal_fecha(datos.get("fecha_fin"))

        if not titulo or len(titulo) > 150:
            return _cal_error("Título obligatorio (máximo 150 caracteres).")

        if len(lugar) > 150:
            return _cal_error("Lugar demasiado largo.")

        if tipo not in COLORES_CALENDARIO:
            return _cal_error("Tipo de evento inválido.")

        if fin <= inicio:
            return _cal_error(
                "La fecha de término debe ser posterior al inicio."
            )

        if alcance not in ("asignatura", "curso"):
            return _cal_error(
                "Los profesores solo pueden publicar eventos "
                "de sus asignaturas o cursos asignados."
            )

        asignacion = None
        curso = None

        if alcance == "asignatura":
            try:
                asignacion_id = int(datos.get("id_asig_curso"))
            except (TypeError, ValueError):
                return _cal_error("Selecciona una asignatura.")

            asignacion = _cal_asignaciones_profesor(
                request
            ).filter(
                id_asig_curso=asignacion_id
            ).first()

            if asignacion is None:
                return _cal_error(
                    "No tienes asignada esa asignatura y curso.",
                    403
                )

        elif alcance == "curso":
            try:
                curso_id = int(datos.get("id_curso"))
            except (TypeError, ValueError):
                return _cal_error("Selecciona un curso.")

            curso = Curso.objects.filter(
                id_curso=curso_id,
                usuario_rut_id=rut_profesor
            ).first()

            if curso is None:
                return _cal_error(
                    "Solo puedes publicar eventos para "
                    "el curso donde eres profesor jefe.",
                    403
                )

        evento_id = datos.get("id_evento")

        with transaction.atomic():
            if evento_id:
                evento = EventoCalendario.objects.select_for_update().filter(
                    id_evento=evento_id,
                    usuario_rut_id=rut_profesor
                ).first()

                if evento is None:
                    return _cal_error(
                        "No puedes modificar este evento.", 403
                    )

                if evento.alcance == "general":
                    return _cal_error(
                        "No puedes modificar eventos generales.", 403
                    )

            else:
                evento = EventoCalendario(
                    usuario_rut_id=rut_profesor
                )

            evento.titulo = titulo
            evento.descripcion = descripcion
            evento.lugar = lugar
            evento.tipo_evento = tipo
            evento.alcance = alcance
            evento.fecha_inicio = inicio
            evento.fecha_fin = fin
            evento.id_asig_curso = asignacion
            evento.id_curso = curso

            if evento_id:
                evento.save()
            else:
                from django.db import connection
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO evento_calendario
                        (titulo, descripcion, fecha_inicio, fecha_fin,
                         tipo_evento, alcance, id_asig_curso, id_curso,
                         usuario_rut, lugar)
                        VALUES (%s, %s, %s, %s, %s, %s,
                                %s, %s, %s, %s)
                        """,
                        [
                            titulo, descripcion, inicio, fin,
                            tipo, alcance,
                            asignacion.id_asig_curso if asignacion else None,
                            curso.id_curso if curso else None,
                            rut_profesor, lugar
                        ]
                    )
                    evento.id_evento = cursor.lastrowid

        return JsonResponse({
            "ok": True,
            "id": evento.id_evento,
            "mensaje": "Evento guardado correctamente."
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return _cal_error("Revisa los datos del evento.")
    except Exception:
        logger_calendario.exception("Error al guardar evento")
        return _cal_error(
            "No se pudo guardar el evento.", 500
        )


@require_role([2])
@require_POST
def profesor_calendario_eliminar(request):
    rut_profesor = request.session.get("usuario_rut")

    if not rut_profesor:
        return _cal_error("Sesión no válida.", 403)

    try:
        datos = json.loads(request.body)
        evento_id = datos.get("id_evento")

        if not evento_id:
            return _cal_error("Falta el ID del evento.")

        evento = EventoCalendario.objects.filter(
            id_evento=evento_id,
            usuario_rut_id=rut_profesor
        ).exclude(alcance="general").first()

        if evento is None:
            return _cal_error(
                "No puedes eliminar este evento.", 403
            )

        evento.delete()

        return JsonResponse({
            "ok": True,
            "mensaje": "Evento eliminado."
        })

    except (ValueError, TypeError, json.JSONDecodeError):
        return _cal_error("Solicitud inválida.")
    except Exception:
        logger_calendario.exception("Error al eliminar evento")
        return _cal_error(
            "No se pudo eliminar el evento.", 500
        )