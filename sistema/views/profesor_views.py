import json
from decimal import Decimal, InvalidOperation
from datetime import date

from django.db import transaction, connection
from django.db.models import Count, Q, Avg, OuterRef, Subquery, Max
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from sistema.models import (
    Curso,
    Alumno,
    AsignaturaCurso,
    Evaluacion,
    Calificacion,
    RegistroAsistencia,
    SolicitudInsumo,
    TicketSoporte,
    EquipoTi,
    Usuario
)
from .auth_views import require_role


@require_role([2])
def profesor_inicio(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    rol = request.session.get('rol_id')
    if rol not in [1, 2, 3]:
        messages.error(request, 'No tienes permisos para acceder a este portal.')
        return redirect('login')
        
    hoy = timezone.localdate()
    rut_profesor = request.session.get('usuario_rut')

    total_cursos = Curso.objects.count()
    total_alumnos = Alumno.objects.count()

    asistencia_hoy = (
        RegistroAsistencia.objects
        .filter(fecha=hoy)
        .values('alumno_rut_alumno_id')
        .annotate(
            presente_hoy=Count(
                'id_asistencia',
                filter=Q(presente=1)
            ),
            ausente_hoy=Count(
                'id_asistencia',
                filter=Q(presente=0)
            )
        )
    )

    presentes_hoy = 0
    ausentes_hoy = 0

    for registro in asistencia_hoy:
        if registro['ausente_hoy'] > 0:
            ausentes_hoy += 1
        elif registro['presente_hoy'] > 0:
            presentes_hoy += 1

    total_asistencia = presentes_hoy + ausentes_hoy

    porcentaje_asistencia = (
        round(presentes_hoy * 100 / total_asistencia)
        if total_asistencia > 0
        else None
    )

    total_evaluaciones = Calificacion.objects.filter(
        valor_nota__isnull=False
    ).count()

    solicitudes = SolicitudInsumo.objects.filter(
        usuario_rut=rut_profesor
    )

    tickets = TicketSoporte.objects.filter(
        usuario_rut_id=rut_profesor
    )

    total_incidencias = solicitudes.count() + tickets.count()

    incidencias_pendientes = (
        solicitudes.filter(
            estado_solicitud__iexact='Pendiente'
        ).count()
        +
        tickets.filter(
            estado_ticket__iexact='Pendiente'
        ).count()
    )

    return render(request, 'profesor_inicio.html', {
        'total_cursos': total_cursos,
        'total_alumnos': total_alumnos,
        'porcentaje_asistencia': porcentaje_asistencia,
        'presentes_hoy': presentes_hoy,
        'ausentes_hoy': ausentes_hoy,
        'total_evaluaciones': total_evaluaciones,
        'total_incidencias': total_incidencias,
        'incidencias_pendientes': incidencias_pendientes,
    })


@require_role([2])
@require_http_methods(["GET", "POST"])
def profesor_notas(request):
    rut_profesor = request.session.get("usuario_rut")

    if not rut_profesor:
        return JsonResponse({
            "ok": False,
            "error": "La sesión del profesor no es válida."
        }, status=403)

    relaciones_permitidas = (
        AsignaturaCurso.objects.filter(
            Q(usuario_rut_id=rut_profesor)
            | Q(curso_id_curso__usuario_rut_id=rut_profesor)
        )
        .select_related(
            "curso_id_curso",
            "asignatura_id_asignatura"
        )
        .distinct()
    )

    if request.method == "POST":
        try:
            payload = json.loads(request.body)

            curso_id = int(payload["curso_id"])
            relacion_id = int(payload["asignatura_id"])

            columnas = payload["columnas"]
            notas = payload["notas"]

            if (
                not isinstance(columnas, list)
                or not 1 <= len(columnas) <= 40
                or not isinstance(notas, dict)
            ):
                raise ValueError("Datos inválidos.")

            if columnas != list(range(1, len(columnas) + 1)):
                raise ValueError(
                    "Las evaluaciones deben ser consecutivas."
                )

        except (
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ):
            return JsonResponse({
                "ok": False,
                "error": "Datos de solicitud inválidos."
            }, status=400)

        relacion = relaciones_permitidas.filter(
            id_asig_curso=relacion_id,
            curso_id_curso_id=curso_id
        ).first()

        if relacion is None:
            return JsonResponse({
                "ok": False,
                "error": (
                    "No tienes permiso para modificar "
                    "esta asignatura o curso."
                )
            }, status=403)

        ruts_validos = set(
            Alumno.objects.filter(
                curso_id_curso_id=curso_id
            ).values_list("rut_alumno", flat=True)
        )

        if set(notas.keys()) != ruts_validos:
            return JsonResponse({
                "ok": False,
                "error": (
                    "La lista de alumnos enviada "
                    "no corresponde al curso."
                )
            }, status=400)

        notas_procesadas = {}

        for rut, valores in notas.items():
            if (
                not isinstance(valores, list)
                or len(valores) != len(columnas)
            ):
                return JsonResponse({
                    "ok": False,
                    "error": (
                        f"Cantidad de notas inválida "
                        f"para el alumno {rut}."
                    )
                }, status=400)

            for numero, valor in enumerate(valores, 1):
                if valor is None or valor == "":
                    continue

                try:
                    numero_nota = Decimal(
                        str(valor).replace(",", ".")
                    )

                except (InvalidOperation, ValueError):
                    return JsonResponse({
                        "ok": False,
                        "error": (
                            f"Nota inválida para el alumno {rut}."
                        )
                    }, status=400)

                if (
                    not numero_nota.is_finite()
                    or numero_nota < Decimal("1.0")
                    or numero_nota > Decimal("7.0")
                    or numero_nota.as_tuple().exponent < -1
                ):
                    return JsonResponse({
                        "ok": False,
                        "error": (
                            "Las notas deben estar entre "
                            "1.0 y 7.0, con máximo un decimal."
                        )
                    }, status=400)

                notas_procesadas[(rut, numero)] = numero_nota

        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id_asig_curso
                        FROM asignatura_curso
                        WHERE id_asig_curso = %s
                        FOR UPDATE
                        """,
                        [relacion_id]
                    )

                    cursor.execute(
                        """
                        SELECT COALESCE(
                            MAX(id_calificacion), 0
                        )
                        FROM calificacion
                        """
                    )

                    max_id = cursor.fetchone()[0]

                evaluaciones_existentes = {
                    evaluacion.numero_evaluacion: evaluacion
                    for evaluacion in Evaluacion.objects.filter(
                        asignatura_curso_id_asig_curso_id=relacion_id
                    )
                }

                cambios = 0
                evaluaciones_creadas = 0
                evaluaciones_eliminadas = 0
                notas_creadas = 0
                notas_actualizadas = 0
                notas_eliminadas = 0

                for numero in columnas:
                    if numero not in evaluaciones_existentes:
                        evaluacion = Evaluacion.objects.create(
                            asignatura_curso_id_asig_curso_id=relacion_id,
                            numero_evaluacion=numero
                        )
                        evaluaciones_existentes[numero] = evaluacion
                        cambios += 1
                        evaluaciones_creadas += 1

                for numero, evaluacion in list(
                    evaluaciones_existentes.items()
                ):
                    if numero not in columnas:
                        calificaciones_eliminadas, _ = (
                            Calificacion.objects.filter(
                                asignatura_curso_id_asig_curso_id=relacion_id,
                                evaluacion_id_evaluacion_id=(
                                    evaluacion.id_evaluacion
                                )
                            ).delete()
                        )
                        notas_eliminadas += calificaciones_eliminadas
                        evaluacion.delete()
                        del evaluaciones_existentes[numero]
                        cambios += 1
                        evaluaciones_eliminadas += 1

                calificaciones_actuales = {}

                registros = (
                    Calificacion.objects.filter(
                        asignatura_curso_id_asig_curso_id=relacion_id,
                        alumno_rut_alumno_id__in=ruts_validos
                    )
                    .select_related("evaluacion_id_evaluacion")
                    .order_by("id_calificacion")
                )

                for calificacion in registros:
                    evaluacion = calificacion.evaluacion_id_evaluacion

                    if evaluacion is None:
                        continue

                    clave = (
                        calificacion.alumno_rut_alumno_id,
                        evaluacion.numero_evaluacion
                    )

                    if clave in calificaciones_actuales:
                        raise ValueError(
                            "Existen calificaciones duplicadas."
                        )

                    calificaciones_actuales[clave] = calificacion

                for clave, nota in notas_procesadas.items():
                    rut_alumno, numero = clave

                    if clave in calificaciones_actuales:
                        calificacion = calificaciones_actuales.pop(clave)

                        valor_actual = (
                            Decimal(str(calificacion.valor_nota))
                            if calificacion.valor_nota is not None
                            else None
                        )

                        if valor_actual != nota:
                            calificacion.valor_nota = nota
                            calificacion.fecha_ingreso = (
                                timezone.localdate()
                            )
                            calificacion.save(
                                update_fields=[
                                    "valor_nota",
                                    "fecha_ingreso"
                                ]
                            )
                            cambios += 1
                            notas_actualizadas += 1
                    else:
                        max_id += 1
                        Calificacion.objects.create(
                            id_calificacion=max_id,
                            valor_nota=nota,
                            fecha_ingreso=timezone.localdate(),
                            alumno_rut_alumno_id=rut_alumno,
                            asignatura_curso_id_asig_curso_id=relacion_id,
                            evaluacion_id_evaluacion_id=(
                                evaluaciones_existentes[
                                    numero
                                ].id_evaluacion
                            )
                        )
                        cambios += 1
                        notas_creadas += 1

                for calificacion in calificaciones_actuales.values():
                    calificacion.delete()
                    cambios += 1
                    notas_eliminadas += 1

        except Exception:
            return JsonResponse({
                "ok": False,
                "error": (
                    "No se pudieron guardar las notas. "
                    "Revisa los datos o la conexión con MySQL."
                )
            }, status=500)

        if cambios == 0:
            return JsonResponse({
                "ok": True,
                "sin_cambios": True,
                "cambios": 0,
                "mensaje": (
                    "No se encontraron cambios. "
                    "Las calificaciones ya están actualizadas."
                )
            })

        return JsonResponse({
            "ok": True,
            "sin_cambios": False,
            "cambios": cambios,
            "evaluaciones_creadas": evaluaciones_creadas,
            "evaluaciones_eliminadas": evaluaciones_eliminadas,
            "notas_creadas": notas_creadas,
            "notas_actualizadas": notas_actualizadas,
            "notas_eliminadas": notas_eliminadas,
            "mensaje": "Calificaciones guardadas correctamente."
        })

    cursos_jefatura = list(
        Curso.objects.filter(
            usuario_rut_id=rut_profesor
        ).order_by("nombre_curso")
    )

    asignaturas_propias = (
        AsignaturaCurso.objects.filter(
            usuario_rut_id=rut_profesor
        )
        .select_related("asignatura_id_asignatura")
        .order_by(
            "asignatura_id_asignatura__nombre_asignatura"
        )
    )

    asignaturas_propias_por_curso = {}

    for relacion in asignaturas_propias:
        clave = str(relacion.curso_id_curso_id)

        asignaturas_propias_por_curso.setdefault(
            clave, []
        ).append({
            "id": str(relacion.id_asig_curso),
            "nombre": (
                relacion.asignatura_id_asignatura.nombre_asignatura
            )
        })

    cursos_asignados = Curso.objects.filter(
        id_curso__in=asignaturas_propias.values_list(
            "curso_id_curso_id",
            flat=True
        )
    ).order_by("nombre_curso")

    relaciones = list(
        relaciones_permitidas.order_by(
            "curso_id_curso__nombre_curso",
            "asignatura_id_asignatura__nombre_asignatura"
        )
    )

    ids_cursos = {
        relacion.curso_id_curso_id
        for relacion in relaciones
    }

    cursos = Curso.objects.filter(
        id_curso__in=ids_cursos
    ).order_by("nombre_curso")

    asignaturas_por_curso = {}

    for relacion in relaciones:
        clave = str(relacion.curso_id_curso_id)

        asignaturas_por_curso.setdefault(
            clave, []
        ).append({
            "id": str(relacion.id_asig_curso),
            "nombre": (
                relacion.asignatura_id_asignatura.nombre_asignatura
            )
        })

    curso_id = request.GET.get("curso", "").strip()

    asignatura_curso_id = request.GET.get(
        "asignatura", ""
    ).strip()

    modo = request.GET.get("modo", "").strip()

    if modo not in ("asignado", "jefatura"):
        modo = ""

    if not curso_id:
        if cursos_jefatura:
            curso_id = str(cursos_jefatura[0].id_curso)
        else:
            primer_curso = cursos.first()

            if primer_curso:
                curso_id = str(primer_curso.id_curso)

    curso_seleccionado = None

    if curso_id.isdigit():
        curso_seleccionado = cursos.filter(
            id_curso=int(curso_id)
        ).first()

    asignatura_seleccionada = None

    alumnos = []
    columnas = [1, 2, 3]
    notas_guardadas = {}

    if curso_seleccionado:
        es_jefatura = (
            curso_seleccionado.usuario_rut_id == rut_profesor
        )

        if modo == "jefatura" and es_jefatura:
            asignaturas_disponibles = (
                relaciones_permitidas.filter(
                    curso_id_curso=curso_seleccionado
                )
            )

        elif modo == "asignado":
            asignaturas_disponibles = (
                relaciones_permitidas.filter(
                    curso_id_curso=curso_seleccionado,
                    usuario_rut_id=rut_profesor
                )
            )

        else:
            asignaturas_disponibles = (
                relaciones_permitidas.filter(
                    curso_id_curso=curso_seleccionado
                )
            )

        asignaturas_disponibles = (
            asignaturas_disponibles.order_by(
                "asignatura_id_asignatura__nombre_asignatura"
            )
        )

        if asignatura_curso_id.isdigit():
            asignatura_seleccionada = (
                asignaturas_disponibles.filter(
                    id_asig_curso=int(asignatura_curso_id)
                ).first()
            )

        elif not asignatura_curso_id:
            asignatura_seleccionada = (
                asignaturas_disponibles.first()
            )

        if asignatura_seleccionada:
            alumnos = list(
                Alumno.objects.filter(
                    curso_id_curso=curso_seleccionado
                ).order_by(
                    "nombre_completo",
                    "rut_alumno"
                )
            )

            evaluaciones = list(
                Evaluacion.objects.filter(
                    asignatura_curso_id_asig_curso=(
                        asignatura_seleccionada
                    )
                ).order_by("numero_evaluacion")
            )

            if evaluaciones:
                max_numero = max(
                    evaluacion.numero_evaluacion
                    for evaluacion in evaluaciones
                )

                columnas = list(range(1, max_numero + 1))

            else:
                columnas = [1, 2, 3]

            numeros = {
                evaluacion.id_evaluacion: (
                    evaluacion.numero_evaluacion
                )
                for evaluacion in evaluaciones
            }

            calificaciones = Calificacion.objects.filter(
                asignatura_curso_id_asig_curso=(
                    asignatura_seleccionada
                ),
                evaluacion_id_evaluacion_id__in=numeros
            )

            for calificacion in calificaciones:
                rut_alumno = (
                    calificacion.alumno_rut_alumno_id
                )

                numero_evaluacion = numeros[
                    calificacion.evaluacion_id_evaluacion_id
                ]

                if calificacion.valor_nota is None:
                    continue

                notas_guardadas.setdefault(
                    rut_alumno, {}
                )[
                    str(numero_evaluacion)
                ] = f"{calificacion.valor_nota:.1f}"

    return render(
        request,
        "profesor_notas.html",
        {
            "cursos": cursos,
            "cursos_asignados": cursos_asignados,
            "cursos_jefatura": cursos_jefatura,
            "asignaturas_por_curso": asignaturas_por_curso,
            "asignaturas_propias_por_curso": (
                asignaturas_propias_por_curso
            ),
            "curso_seleccionado": curso_seleccionado,
            "asignatura_seleccionada": (
                asignatura_seleccionada
            ),
            "alumnos": alumnos,
            "columnas": columnas,
            "notas_guardadas": notas_guardadas,
            "modo": modo,
        }
    )


@require_role([2])
@require_http_methods(["GET", "POST"])
def profesor_asistencia(request):
    rut_profesor = request.session.get("usuario_rut")

    if not rut_profesor:
        return JsonResponse({
            "ok": False,
            "error": "Sesión inválida."
        }, status=403)

    hoy = timezone.localdate()

    relaciones_permitidas = (
        AsignaturaCurso.objects.filter(
            Q(usuario_rut_id=rut_profesor)
            | Q(curso_id_curso__usuario_rut_id=rut_profesor)
        ).distinct()
    )

    if request.method == "POST":
        try:
            datos = json.loads(request.body)

            fecha = date.fromisoformat(datos["fecha"])
            curso_id = int(datos["curso_id"])
            asignatura_id = int(datos["asignatura_id"])
            estados = datos["estados"]

            if fecha != hoy:
                return JsonResponse({
                    "ok": False,
                    "error": (
                        "Solo puedes registrar o modificar "
                        "la asistencia del día actual."
                    )
                }, status=400)

            if not isinstance(estados, dict):
                raise ValueError(
                    "Formato de asistencia inválido."
                )

            asignatura = relaciones_permitidas.filter(
                id_asig_curso=asignatura_id,
                curso_id_curso_id=curso_id
            ).first()

            if asignatura is None:
                return JsonResponse({
                    "ok": False,
                    "error": (
                        "No tienes permiso para registrar "
                        "asistencia en esta asignatura."
                    )
                }, status=403)

            ruts_validos = set(
                Alumno.objects.filter(
                    curso_id_curso_id=curso_id
                ).values_list(
                    "rut_alumno",
                    flat=True
                )
            )

            if (
                not ruts_validos
                or set(estados.keys()) != ruts_validos
            ):
                return JsonResponse({
                    "ok": False,
                    "error": (
                        "Debes registrar la asistencia "
                        "de todos los alumnos del curso."
                    )
                }, status=400)

            for estado in estados.values():
                if type(estado) is not int or estado not in (0, 1):
                    return JsonResponse({
                        "ok": False,
                        "error": (
                            "Todos los alumnos deben estar "
                            "marcados como presentes o ausentes."
                        )
                    }, status=400)

        except (
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
        ) as error:
            return JsonResponse({
                "ok": False,
                "error": f"Solicitud inválida: {error}"
            }, status=400)

        try:
            with transaction.atomic():
                Curso.objects.select_for_update().get(
                    id_curso=curso_id
                )

                registros = list(
                    RegistroAsistencia.objects
                    .select_for_update()
                    .filter(
                        fecha=fecha,
                        alumno_rut_alumno_id__in=ruts_validos,
                        asignatura_curso_id_asig_curso__curso_id_curso_id=curso_id
                    )
                    .order_by("id_asistencia")
                )

                registros_por_alumno = {}

                for registro in registros:
                    rut = registro.alumno_rut_alumno_id

                    registros_por_alumno.setdefault(
                        rut, []
                    ).append(registro)

                max_id = (
                    RegistroAsistencia.objects.aggregate(
                        max_id=Max("id_asistencia")
                    )["max_id"] or 0
                )

                for rut, estado in estados.items():
                    existentes = (
                        registros_por_alumno.get(rut, [])
                    )

                    if existentes:
                        for registro in existentes:
                            if registro.presente != estado:
                                registro.presente = estado
                                registro.save(
                                    update_fields=["presente"]
                                )
                    else:
                        max_id += 1

                        RegistroAsistencia.objects.create(
                            id_asistencia=max_id,
                            fecha=fecha,
                            presente=estado,
                            alumno_rut_alumno_id=rut,
                            asignatura_curso_id_asig_curso_id=asignatura_id
                        )

            return JsonResponse({
                "ok": True,
                "mensaje": (
                    "La asistencia del curso fue guardada "
                    "correctamente y se reflejará en "
                    "todas sus asignaturas."
                )
            })

        except Exception:
            return JsonResponse({
                "ok": False,
                "error": (
                    "No fue posible guardar la asistencia. "
                    "Revisa la conexión con MySQL."
                )
            }, status=500)

    cursos_jefatura = list(
        Curso.objects.filter(
            usuario_rut_id=rut_profesor
        ).order_by("nombre_curso")
    )

    asignaturas_propias = (
        AsignaturaCurso.objects.filter(
            usuario_rut_id=rut_profesor
        )
        .select_related("asignatura_id_asignatura")
        .order_by(
            "asignatura_id_asignatura__nombre_asignatura"
        )
    )

    asignaturas_propias_por_curso = {}

    for relacion in asignaturas_propias:
        clave = str(relacion.curso_id_curso_id)

        asignaturas_propias_por_curso.setdefault(
            clave, []
        ).append({
            "id": str(relacion.id_asig_curso),
            "nombre": (
                relacion.asignatura_id_asignatura.nombre_asignatura
            )
        })

    cursos_asignados = Curso.objects.filter(
        id_curso__in=asignaturas_propias.values_list(
            "curso_id_curso_id",
            flat=True
        )
    ).order_by("nombre_curso")

    relaciones = list(
        relaciones_permitidas
        .select_related(
            "curso_id_curso",
            "asignatura_id_asignatura"
        )
        .order_by(
            "curso_id_curso__nombre_curso",
            "asignatura_id_asignatura__nombre_asignatura"
        )
    )

    asignaturas_por_curso = {}

    for relacion in relaciones:
        clave = str(relacion.curso_id_curso_id)

        asignaturas_por_curso.setdefault(
            clave, []
        ).append({
            "id": str(relacion.id_asig_curso),
            "nombre": (
                relacion.asignatura_id_asignatura.nombre_asignatura
            )
        })

    ids_cursos = {
        relacion.curso_id_curso_id
        for relacion in relaciones
    }

    cursos = Curso.objects.filter(
        id_curso__in=ids_cursos
    ).order_by("nombre_curso")

    curso_id = request.GET.get("curso", "").strip()
    asignatura_id = request.GET.get(
        "asignatura", ""
    ).strip()

    modo = request.GET.get("modo", "").strip()

    if modo not in ("asignado", "jefatura"):
        modo = ""

    fecha_texto = request.GET.get("fecha", "").strip()

    try:
        fecha = (
            date.fromisoformat(fecha_texto)
            if fecha_texto
            else hoy
        )
    except ValueError:
        fecha = hoy
        messages.error(
            request,
            "La fecha ingresada no es válida."
        )

    if not curso_id:
        if cursos_jefatura:
            curso_id = str(
                cursos_jefatura[0].id_curso
            )
        else:
            primer_curso = cursos.first()

            if primer_curso:
                curso_id = str(
                    primer_curso.id_curso
                )

    curso_seleccionado = None

    if curso_id.isdigit():
        curso_seleccionado = cursos.filter(
            id_curso=int(curso_id)
        ).first()

    asignatura_seleccionada = None
    asignaturas = AsignaturaCurso.objects.none()

    alumnos = []

    presentes = 0
    ausentes = 0

    asistencia_guardada = False
    asistencia_completa = False
    registros_inconsistentes = False

    if curso_seleccionado:
        es_jefatura = (
            curso_seleccionado.usuario_rut_id
            == rut_profesor
        )

        if modo == "jefatura" and es_jefatura:
            asignaturas = relaciones_permitidas.filter(
                curso_id_curso=curso_seleccionado
            )

        elif modo == "asignado":
            asignaturas = relaciones_permitidas.filter(
                curso_id_curso=curso_seleccionado,
                usuario_rut_id=rut_profesor
            )

        else:
            asignaturas = relaciones_permitidas.filter(
                curso_id_curso=curso_seleccionado
            )

        asignaturas = (
            asignaturas
            .select_related("asignatura_id_asignatura")
            .order_by(
                "asignatura_id_asignatura__nombre_asignatura"
            )
        )

        if asignatura_id.isdigit():
            asignatura_seleccionada = (
                asignaturas.filter(
                    id_asig_curso=int(asignatura_id)
                ).first()
            )

        elif not asignatura_id:
            asignatura_seleccionada = asignaturas.first()

        if asignatura_seleccionada:
            alumnos = list(
                Alumno.objects.filter(
                    curso_id_curso=curso_seleccionado
                ).order_by(
                    "nombre_completo",
                    "rut_alumno"
                )
            )

            ruts = [
                alumno.rut_alumno
                for alumno in alumnos
            ]

            registros = (
                RegistroAsistencia.objects.filter(
                    fecha=fecha,
                    alumno_rut_alumno_id__in=ruts,
                    asignatura_curso_id_asig_curso__curso_id_curso_id=(
                        curso_seleccionado.id_curso
                    )
                )
                .order_by("-id_asistencia")
            )

            estados_guardados = {}
            estados_encontrados = {}

            for registro in registros:
                rut = registro.alumno_rut_alumno_id

                estados_encontrados.setdefault(
                    rut, set()
                ).add(registro.presente)

                if rut not in estados_guardados:
                    estados_guardados[rut] = registro.presente

            registros_inconsistentes = any(
                len(estados) > 1
                for estados in estados_encontrados.values()
            )

            for alumno in alumnos:
                alumno.estado_asistencia = (
                    estados_guardados.get(
                        alumno.rut_alumno
                    )
                )

                if alumno.estado_asistencia == 1:
                    presentes += 1

                elif alumno.estado_asistencia == 0:
                    ausentes += 1

            asistencia_guardada = bool(
                estados_guardados
            )

            asistencia_completa = (
                len(alumnos) > 0
                and len(estados_guardados) == len(alumnos)
                and not registros_inconsistentes
            )

    return render(
        request,
        "profesor_asistencia.html",
        {
            "cursos": cursos,
            "cursos_asignados": cursos_asignados,
            "cursos_jefatura": cursos_jefatura,
            "asignaturas_por_curso": (
                asignaturas_por_curso
            ),
            "asignaturas_propias_por_curso": (
                asignaturas_propias_por_curso
            ),
            "curso_seleccionado": curso_seleccionado,
            "asignaturas": asignaturas,
            "asignatura_seleccionada": (
                asignatura_seleccionada
            ),
            "modo": modo,
            "fecha_seleccionada": fecha.isoformat(),
            "fecha_actual": hoy.isoformat(),
            "alumnos": alumnos,
            "total_alumnos": len(alumnos),
            "presentes": presentes,
            "ausentes": ausentes,
            "asistencia_guardada": asistencia_guardada,
            "asistencia_completa": asistencia_completa,
            "registros_inconsistentes": (
                registros_inconsistentes
            ),
        }
    )


@require_role([2])
def profesor_agregar_incidencia(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    equipos = list(
        EquipoTi.objects.all().order_by('codigo_inventario')
    )

    tipos_equipos = {
        'PC': 'Computador',
        'NOTE': 'Notebook',
        'MOU': 'Mouse',
        'TEC': 'Teclado',
        'PROY': 'Proyector',
        'IMP': 'Impresora',
        'USB': 'Pendrive',
        'ROUT': 'Router',
        'MON': 'Monitor',
        'HDMI': 'Cable HDMI',
        'EXT': 'Alargador eléctrico',
    }

    for equipo in equipos:
        prefijo = equipo.codigo_inventario.split('-')[0].upper()
        equipo.nombre_equipo = tipos_equipos.get(
            prefijo,
            'Equipo tecnológico'
        )

    if request.method == 'POST':
        tipo = request.POST.get('tipo') or request.POST.get('tipo_incidencia') or ''
        descripcion = request.POST.get('descripcion', '').strip()
        prioridad = request.POST.get('prioridad', 'Media')
        rut_usuario = request.session.get('usuario_rut')
        fecha = request.POST.get('fecha') or date.today()
        codigo_equipo = request.POST.get('equipo', '').strip()

        es_aseo = tipo in ['material', 'reposicion', 'Solicitud de Material', 'Solicitud de Reposición']

        if not descripcion:
            messages.error(request, 'Debes ingresar una descripción.')
            return redirect('profesor_agregar_incidencia')

        if es_aseo:
            res = SolicitudInsumo.objects.aggregate(max_val=Max('id_solicitud'))
            nuevo_id = (res.get('max_val') or 0) + 1

            SolicitudInsumo.objects.create(
                id_solicitud=nuevo_id,
                fecha=fecha,
                estado_solicitud='Pendiente',
                usuario_rut_id=rut_usuario,
                descripcion=descripcion,
                tipo_solicitud='Solicitud de Material' if tipo == 'material' else tipo
            )
            messages.success(request, '¡Solicitud de aseo enviada con éxito!')
            return redirect('profesor_gestion_incidencias')

        else:
            equipo_obj = None
            if codigo_equipo:
                equipo_obj = EquipoTi.objects.filter(
                    codigo_inventario=codigo_equipo
                ).first()
            
            if not equipo_obj:
                equipo_obj = EquipoTi.objects.filter(
                    codigo_inventario='EXT-001'
                ).first()

            res = TicketSoporte.objects.aggregate(max_val=Max('id_ticket'))
            nuevo_id_ticket = (res.get('max_val') or 0) + 1

            TicketSoporte.objects.create(
                id_ticket=nuevo_id_ticket,
                fecha_reporte=fecha,
                prioridad=prioridad,
                estado_ticket='Pendiente',
                usuario_rut_id=rut_usuario,
                descripcion=descripcion,
                tipo_incidencia=tipo,
                equipo_ti_codigo_inventario=equipo_obj
            )
            messages.success(request, '¡Incidencia de TI registrada con éxito!')
            return redirect('profesor_gestion_incidencias')

    return render(request, 'profesor_agregar_incidencia.html', {
        'equipos': equipos,
        'fecha_actual': timezone.localdate().isoformat()
    })


@require_role([2])
def profesor_gestion_incidencias(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    rut_profesor = request.session.get('usuario_rut')
    
    incidencias_ti = TicketSoporte.objects.filter(usuario_rut_id=rut_profesor).order_by('-id_ticket')
    solicitudes_aseo = SolicitudInsumo.objects.filter(usuario_rut=rut_profesor).order_by('-id_solicitud')
    
    context = {
        'incidencias_ti': incidencias_ti,
        'solicitudes_aseo': solicitudes_aseo,
    }
    return render(request, 'profesor_gestion_incidencias.html', context)


@require_role([2])
def profesor_detalle_incidencia(request, pk):
    rut_profesor = request.session.get('usuario_rut')
    ticket = get_object_or_404(TicketSoporte, pk=pk, usuario_rut__rut=rut_profesor)
    
    context = {
        'ticket': ticket
    }
    return render(request, 'profesor_detalle_incidencia.html', context)


@require_role([2])
def profesor_alumnos(request):
    cursos = Curso.objects.all().order_by('id_curso')

    curso_id = request.GET.get('curso', '').strip()
    asignatura_id = request.GET.get('asignatura', '').strip()

    curso_seleccionado = None
    asignatura_seleccionada = None

    alumnos = Alumno.objects.none()
    asignaturas = AsignaturaCurso.objects.none()

    if curso_id.isdigit():
        curso_seleccionado = cursos.filter(
            id_curso=int(curso_id)
        ).first()

        if curso_seleccionado:
            alumnos = (
                Alumno.objects.filter(
                    curso_id_curso=curso_seleccionado
                )
                .select_related('usuario_rut')
                .order_by('nombre_completo')
            )

            asignaturas = (
                AsignaturaCurso.objects.filter(
                    curso_id_curso=curso_seleccionado
                )
                .select_related('asignatura_id_asignatura')
                .order_by(
                    'asignatura_id_asignatura__nombre_asignatura'
                )
            )

            if asignatura_id.isdigit():
                asignatura_seleccionada = asignaturas.filter(
                    id_asig_curso=int(asignatura_id)
                ).first()

                if asignatura_seleccionada:
                    promedio_subconsulta = (
                        Calificacion.objects.filter(
                            alumno_rut_alumno_id=OuterRef('rut_alumno'),
                            asignatura_curso_id_asig_curso=asignatura_seleccionada
                        )
                        .values('alumno_rut_alumno_id')
                        .annotate(promedio=Avg('valor_nota'))
                        .values('promedio')[:1]
                    )

                    alumnos = alumnos.annotate(
                        promedio_asignatura=Subquery(
                            promedio_subconsulta
                        )
                    )

    elif curso_id:
        messages.error(
            request,
            'El curso seleccionado no es válido.'
        )

    return render(request, 'profesor_alumnos.html', {
        'cursos': cursos,
        'curso_seleccionado': curso_seleccionado,
        'asignaturas': asignaturas,
        'asignatura_seleccionada': asignatura_seleccionada,
        'alumnos': alumnos,
        'total_alumnos': alumnos.count(),
    })


@require_role([2])
def profesor_perfil_alumno(request, rut):
    alumno = get_object_or_404(
        Alumno.objects.select_related('curso_id_curso__usuario_rut', 'usuario_rut'),
        rut_alumno=rut,
    )
    apoderado = alumno.usuario_rut
    profesor_jefe = alumno.curso_id_curso.usuario_rut

    notas = (
        Calificacion.objects
        .filter(alumno_rut_alumno=alumno)
        .values('asignatura_curso_id_asig_curso__asignatura_id_asignatura__nombre_asignatura')
        .annotate(promedio=Avg('valor_nota'), cantidad=Count('id_calificacion'))
        .order_by('asignatura_curso_id_asig_curso__asignatura_id_asignatura__nombre_asignatura')
    )
    promedios = [
        {
            'asignatura': fila['asignatura_curso_id_asig_curso__asignatura_id_asignatura__nombre_asignatura'],
            'promedio': fila['promedio'],
            'cantidad': fila['cantidad'],
        }
        for fila in notas
    ]
    promedio_general = (
        Calificacion.objects.filter(alumno_rut_alumno=alumno)
        .aggregate(promedio=Avg('valor_nota'))['promedio']
    )

    asistencias = RegistroAsistencia.objects.filter(alumno_rut_alumno=alumno)
    total_clases = asistencias.count()
    presentes = asistencias.filter(presente=1).count()
    ausentes = total_clases - presentes
    porcentaje_asistencia = round(presentes * 100 / total_clases, 1) if total_clases else None
    historial = (
        asistencias.select_related('asignatura_curso_id_asig_curso__asignatura_id_asignatura')
        .order_by('-fecha', '-id_asid_asistencia' if hasattr(RegistroAsistencia, 'id_asid_asistencia') else '-id_asistencia')[:15]
    )

    nombre_apoderado = ' '.join(filter(None, [
        apoderado.nombre, apoderado.apellido_paterno, apoderado.apellido_materno
    ])) if apoderado else ''
    nombre_profesor = ' '.join(filter(None, [
        profesor_jefe.nombre, profesor_jefe.apellido_paterno, profesor_jefe.apellido_materno
    ])) if profesor_jefe else ''

    return render(request, 'profesor_perfil_alumno.html', {
        'alumno': alumno,
        'apoderado': apoderado,
        'nombre_apoderado': nombre_apoderado,
        'nombre_profesor': nombre_profesor,
        'promedios': promedios,
        'promedio_general': promedio_general,
        'total_clases': total_clases,
        'presentes': presentes,
        'ausentes': ausentes,
        'porcentaje_asistencia': porcentaje_asistencia,
        'historial_asistencia': historial,
    })