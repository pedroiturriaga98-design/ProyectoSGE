from datetime import datetime
from .models import TicketSoporte, SolicitudInsumo, EquipoTi, Usuario, Rol, Alumno, Curso, AsignaturaCurso
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from functools import wraps # Importante para hacer decoradores
from .models import Usuario, Rol, Alumno, Curso, AsignaturaCurso
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.contrib.auth.hashers import check_password, make_password, identify_hasher


def require_role(roles_permitidos):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. Revisamos si el usuario inició sesión
            if 'usuario_rut' not in request.session:
                messages.error(request, 'Debes iniciar sesión para acceder a esta página.')
                return redirect('login') # Lo mandamos pa' fuera
            
            # 2. Revisamos si su rol está en la lista de permitidos
            rol_actual = request.session.get('rol_id')
            if rol_actual not in roles_permitidos:
                # Si es profe (rol 2) y trata de entrar a admin (rol 1)
                messages.error(request, 'No tienes permisos para ver esta sección.')
                # Lo devolvemos a su menú principal (o lo que consideres)
                return redirect('login') 
            
            # Si todo está OK, lo dejamos pasar a la vista original
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def login_view(request):
    if request.method == 'GET':
        # Consume y limpia cualquier mensaje viejo que haya quedado en sesión
        storage = messages.get_messages(request)
        for _ in storage:
            pass
    
    if request.method == 'POST':
        credencial_ingresada = (
            request.POST.get('username') or ''
        ).strip()

        password_ingresada = request.POST.get('password') or ''

        if not credencial_ingresada or not password_ingresada:
            messages.error(
                request,
                'Debes ingresar tu correo o RUT y contraseña.'
            )
            return render(request, 'login.html')

        try:
            # 1. Buscar al usuario por correo o RUT
            if '@' in credencial_ingresada:
                usuario = Usuario.objects.get(
                    correo__iexact=credencial_ingresada
                )
            else:
                usuario = Usuario.objects.get(
                    rut=credencial_ingresada
                )

            # 2. Comprobar si la contraseña está cifrada
            try:
                identify_hasher(usuario.password_hash)
                password_cifrada = True
            except ValueError:
                password_cifrada = False

            # 3. Validar la contraseña
            if password_cifrada:
                acceso_valido = check_password(
                    password_ingresada,
                    usuario.password_hash
                )
            else:
                # Compatibilidad con cuentas antiguas
                acceso_valido = (
                    usuario.password_hash == password_ingresada
                )

                # Cifrar la contraseña antigua si es correcta
                if acceso_valido:
                    usuario.password_hash = make_password(
                        password_ingresada
                    )
                    usuario.save(
                        update_fields=['password_hash']
                    )

            # 4. Guardar la sesión y redirigir según los roles
            if acceso_valido:
                request.session['ultimo_acceso'] = datetime.now().strftime('%d/%m/%Y a las %H:%M')
                request.session.flush()

                request.session['usuario_rut'] = usuario.rut
                request.session['rol_id'] = usuario.rol_id_rol.id_rol
                request.session['nombre_usuario'] = usuario.nombre
                request.session['apellido_usuario'] = usuario.apellido_paterno
                request.session['rol_nombre'] = usuario.rol_id_rol.nombre_rol

                request.session['ultimo_acceso'] = datetime.now().strftime('%d/%m/%Y a las %H:%M')

                # NUEVO: Si el usuario debe cambiar su contraseña obligatoriamente
                if usuario.cambiar_password:
                    request.session['debe_cambiar_pass'] = True
                    return redirect('cambiar_password_obligatorio')

                # Redirección normal si ya cambió su contraseña antes...
                rol = usuario.rol_id_rol.id_rol
                if rol in [1, 4]:
                    return redirect('admin_inicio')
                elif rol == 2:
                    return redirect('profesor_inicio')
                elif rol == 3:
                    return redirect('apoderado_inicio')
                elif rol == 5:
                    return redirect('inicio_supervisor_aseo')


            else:
                messages.error(
                    request,
                    'Contraseña incorrecta.'
                )

        except Usuario.DoesNotExist:
            messages.error(
                request,
                'El usuario o correo ingresado no existe en el sistema.'
            )

        except Usuario.MultipleObjectsReturned:
            messages.error(
                request,
                'Hay más de una cuenta con ese correo. Contacta al administrador.'
            )

    return render(request, 'login.html')

def validar_rut(rut_str):
    if not rut_str:
        return False

    # Limpiamos puntos, guiones y espacios
    rut_limpio = str(rut_str).replace(".", "").replace("-", "").strip().upper()
    
    # Un RUN chileno tiene entre 8 y 9 caracteres (ej: 8572314K o 195723141)
    if len(rut_limpio) < 8 or len(rut_limpio) > 9:
        return False
    
    cuerpo = rut_limpio[:-1]
    dv = rut_limpio[-1]
    
    # El cuerpo debe contener únicamente dígitos
    if not cuerpo.isdigit():
        return False
    
    # Algoritmo Módulo 11
    suma = 0
    multiplicador = 2
    for digit in reversed(cuerpo):
        suma += int(digit) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    
    resto = suma % 11
    resultado = 11 - resto
    
    if resultado == 11:
        dv_esperado = '0'
    elif resultado == 10:
        dv_esperado = 'K'
    else:
        dv_esperado = str(resultado)
        
    return dv == dv_esperado

# Vistas para el portal de apoderados



@require_role([3])
def apoderado_inicio(request):
    from .models import Alumno

    rut_apoderado = request.session.get('usuario_rut')

    # Alumnos asociados al apoderado.
    # También recuperamos al profesor jefe de cada curso.
    alumnos = list(
        Alumno.objects
        .filter(usuario_rut_id=rut_apoderado)
        .select_related(
            'curso_id_curso',
            'curso_id_curso__usuario_rut'
        )
        .order_by('nombre_completo')
    )

    profesores_jefes = []
    cursos_agregados = set()

    for alumno in alumnos:
        curso = alumno.curso_id_curso

        # Evitar repetir al profesor si dos hijos
        # pertenecen al mismo curso.
        if curso.id_curso in cursos_agregados:
            continue

        cursos_agregados.add(curso.id_curso)

        profesor = curso.usuario_rut

        if profesor:
            nombre_completo = ' '.join(
                parte for parte in [
                    profesor.nombre,
                    profesor.apellido_paterno,
                    profesor.apellido_materno
                ]
                if parte
            )

            profesores_jefes.append({
                'nombre': nombre_completo or 'Sin nombre',
                'correo': profesor.correo,
                'curso': curso.nombre_curso,
                'alumno': alumno.nombre_completo,
            })
        else:
            profesores_jefes.append({
                'nombre': 'Profesor jefe no asignado',
                'correo': None,
                'curso': curso.nombre_curso,
                'alumno': alumno.nombre_completo,
            })

    context = {
        'alumnos': alumnos,
        'apoderado_alumnos': alumnos,
        'total_alumnos': len(alumnos),
        'profesores_jefes': profesores_jefes,
    }

    return render(
        request,
        'apoderado_inicio.html',
        context
    )




@require_role([3])
def apoderado_notas(request):
    from django.http import Http404
    from .models import Alumno, AsignaturaCurso, Calificacion

    rut_apoderado = request.session.get('usuario_rut')

    alumnos = list(
        Alumno.objects
        .filter(usuario_rut_id=rut_apoderado)
        .select_related('curso_id_curso')
        .order_by('nombre_completo')
    )

    rut_solicitado = request.GET.get('alumno', '').strip()

    if rut_solicitado:
        alumno_seleccionado = next(
            (a for a in alumnos if a.rut_alumno == rut_solicitado),
            None
        )

        if alumno_seleccionado is None:
            raise Http404(
                'Estudiante no asociado a este apoderado.'
            )
    else:
        alumno_seleccionado = alumnos[0] if alumnos else None

    resumen_notas = []
    numeros_evaluacion = set()

    if alumno_seleccionado:

        asignaturas = list(
            AsignaturaCurso.objects
            .filter(
                curso_id_curso=alumno_seleccionado.curso_id_curso
            )
            .select_related('asignatura_id_asignatura')
            .order_by(
                'asignatura_id_asignatura__nombre_asignatura'
            )
        )

        calificaciones = (
            Calificacion.objects
            .filter(
                alumno_rut_alumno=alumno_seleccionado,
                asignatura_curso_id_asig_curso__curso_id_curso=
                    alumno_seleccionado.curso_id_curso
            )
            .select_related('evaluacion_id_evaluacion')
            .order_by('fecha_ingreso', 'id_calificacion')
        )

        notas_por_asignatura = {}

        for calificacion in calificaciones:

            id_asignatura = (
                calificacion.asignatura_curso_id_asig_curso_id
            )

            evaluacion = calificacion.evaluacion_id_evaluacion

            if evaluacion is None:
                continue

            numero = evaluacion.numero_evaluacion

            numeros_evaluacion.add(numero)

            if id_asignatura not in notas_por_asignatura:
                notas_por_asignatura[id_asignatura] = {}

            # Si hay registros repetidos de una misma evaluación,
            # se muestra el último según el orden de consulta.
            notas_por_asignatura[id_asignatura][numero] = calificacion

        # Se muestran al menos tres columnas.
        total_columnas = max(
            max(numeros_evaluacion, default=0),
            3
        )

        columnas_notas = list(range(1, total_columnas + 1))

        for asignatura_curso in asignaturas:

            notas_registradas = notas_por_asignatura.get(
                asignatura_curso.id_asig_curso,
                {}
            )

            notas_ordenadas = []

            for numero in columnas_notas:

                calificacion = notas_registradas.get(numero)

                notas_ordenadas.append({
                    'numero': numero,
                    'calificacion': calificacion,
                })

            valores = [
                nota.valor_nota
                for nota in notas_registradas.values()
                if nota.valor_nota is not None
            ]

            promedio = (
                round(sum(valores) / len(valores), 1)
                if valores else None
            )

            resumen_notas.append({
                'nombre_asignatura':
                    asignatura_curso.asignatura_id_asignatura.nombre_asignatura,
                'notas_ordenadas': notas_ordenadas,
                'promedio': promedio,
            })

    else:
        columnas_notas = [1, 2, 3]

    return render(request, 'apoderado_notas.html', {
        'alumnos': alumnos,
        'alumno_seleccionado': alumno_seleccionado,
        'resumen_notas': resumen_notas,
        'columnas_notas': columnas_notas,
        'total_columnas_tabla': len(columnas_notas) + 2,
    })




@require_role([3])
def apoderado_asistencia(request):
    import calendar
    from datetime import date, timedelta
    from django.http import Http404
    from django.utils import timezone

    from .models import Alumno, RegistroAsistencia

    rut_apoderado = request.session.get('usuario_rut')

    alumnos = list(
        Alumno.objects
        .filter(usuario_rut_id=rut_apoderado)
        .select_related('curso_id_curso')
        .order_by('nombre_completo')
    )

    rut_solicitado = request.GET.get('alumno', '').strip()

    if rut_solicitado:
        alumno_seleccionado = next(
            (alumno for alumno in alumnos
             if alumno.rut_alumno == rut_solicitado),
            None
        )

        if alumno_seleccionado is None:
            raise Http404(
                'Estudiante no asociado a este apoderado.'
            )
    else:
        alumno_seleccionado = alumnos[0] if alumnos else None

    hoy = timezone.localdate()

    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))

        if not (1 <= anio <= 9999 and 1 <= mes <= 12):
            raise ValueError

    except (ValueError, TypeError):
        anio = hoy.year
        mes = hoy.month

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(
        anio, mes, calendar.monthrange(anio, mes)[1]
    )

    if mes == 1:
        mes_anterior = 12
        anio_anterior = anio - 1
    else:
        mes_anterior = mes - 1
        anio_anterior = anio

    if mes == 12:
        mes_siguiente = 1
        anio_siguiente = anio + 1
    else:
        mes_siguiente = mes + 1
        anio_siguiente = anio

    nombres_meses = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril',
        'Mayo', 'Junio', 'Julio', 'Agosto',
        'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]

    estados_por_fecha = {}

    if alumno_seleccionado:
        registros = (
            RegistroAsistencia.objects
            .filter(
                alumno_rut_alumno=alumno_seleccionado,
                fecha__range=(primer_dia, ultimo_dia)
            )
            .order_by('-id_asistencia')
        )

        # Una sola asistencia por día.
        # Si existen registros antiguos en distintas asignaturas,
        # se toma el registro con mayor ID.
        for registro in registros:
            if registro.fecha not in estados_por_fecha:
                estados_por_fecha[registro.fecha] = registro.presente

    dias_asistidos = sum(
        1 for estado in estados_por_fecha.values()
        if estado == 1
    )

    inasistencias = sum(
        1 for estado in estados_por_fecha.values()
        if estado == 0
    )

    total_registrados = dias_asistidos + inasistencias

    porcentaje_asistencia = (
        round(dias_asistidos * 100 / total_registrados, 1)
        if total_registrados else None
    )

    # Calendario de lunes a viernes, como el diseño original.
    semanas = []
    calendario = calendar.Calendar(firstweekday=0)

    for semana in calendario.monthdatescalendar(anio, mes):
        dias_semana = []

        for fecha_dia in semana[:5]:

            if fecha_dia.month != mes:
                dias_semana.append({
                    'numero': None,
                    'estado': 'vacio',
                    'texto': ''
                })
                continue

            estado = estados_por_fecha.get(fecha_dia)

            if estado == 1:
                clase = 'presente'
                texto = 'ASISTIÓ'
            elif estado == 0:
                clase = 'ausente'
                texto = 'FALTÓ'
            else:
                clase = 'sin-registro'
                texto = 'SIN REGISTRO'

            dias_semana.append({
                'numero': fecha_dia.day,
                'estado': clase,
                'texto': texto,
                'fecha': fecha_dia
            })

        semanas.append(dias_semana)

    return render(request, 'apoderado_asistencia.html', {
        'alumnos': alumnos,
        'alumno_seleccionado': alumno_seleccionado,
        'nombre_mes': nombres_meses[mes],
        'anio': anio,
        'mes': mes,
        'anio_anterior': anio_anterior,
        'mes_anterior': mes_anterior,
        'anio_siguiente': anio_siguiente,
        'mes_siguiente': mes_siguiente,
        'semanas': semanas,
        'dias_asistidos': dias_asistidos,
        'inasistencias': inasistencias,
        'total_registrados': total_registrados,
        'porcentaje_asistencia': porcentaje_asistencia,
    })



# ============================================================
# CALENDARIO ESCOLAR SGE - MYSQL / FULLCALENDAR
# ============================================================

import json
import logging
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from .models import Alumno, AsignaturaCurso, Curso, EventoCalendario

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


# ------------------------------------------------------------
# VISTA PROFESOR
# ------------------------------------------------------------

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

    # Solamente cursos donde el profesor es jefe.
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


# ------------------------------------------------------------
# VISTA APODERADO
# ------------------------------------------------------------


@require_role([3])
def apoderado_calendario(request):
    from django.http import Http404

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

    # La búsqueda impide consultar alumnos de otro apoderado.
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


# ------------------------------------------------------------
# CREAR / EDITAR EVENTO - PROFESOR
# ------------------------------------------------------------

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

            # Solo permite publicar para cursos
            # donde el profesor es jefe.
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

                # No permite modificar eventos generales
                # desde el portal profesor.
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

            # MySQL aplica DEFAULT CURRENT_TIMESTAMP
            # para los eventos nuevos.
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


# ------------------------------------------------------------
# ELIMINAR EVENTO - PROFESOR
# ------------------------------------------------------------

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



@require_role([3])
def apoderado_certificados(request):
    from collections import defaultdict
    from django.http import Http404
    from django.utils import timezone
    from .models import Alumno, AsignaturaCurso, Calificacion

    rut_apoderado = request.session.get('usuario_rut')

    alumnos = list(
        Alumno.objects
        .filter(usuario_rut_id=rut_apoderado)
        .select_related('curso_id_curso')
        .order_by('nombre_completo')
    )

    rut_solicitado = request.GET.get('alumno', '').strip()

    if rut_solicitado:
        alumno_seleccionado = next(
            (a for a in alumnos if a.rut_alumno == rut_solicitado),
            None
        )
        if alumno_seleccionado is None:
            raise Http404('Estudiante no asociado a este apoderado.')
    else:
        alumno_seleccionado = alumnos[0] if alumnos else None

    tipo_certificado = request.GET.get('tipo', 'regular')
    if tipo_certificado not in ('regular', 'notas'):
        tipo_certificado = 'regular'

    # Por ahora se muestran todas las notas registradas.
    # No se separan por semestre porque todavía no
    # confirmamos cómo se identifica el semestre en MySQL.
    resumen_notas = []
    numeros_evaluacion = set()
    promedios = []

    if alumno_seleccionado and tipo_certificado == 'notas':
        asignaturas = list(
            AsignaturaCurso.objects
            .filter(curso_id_curso=alumno_seleccionado.curso_id_curso)
            .select_related('asignatura_id_asignatura')
            .order_by('asignatura_id_asignatura__nombre_asignatura')
        )

        calificaciones = (
            Calificacion.objects
            .filter(
                alumno_rut_alumno=alumno_seleccionado,
                asignatura_curso_id_asig_curso__curso_id_curso=
                    alumno_seleccionado.curso_id_curso
            )
            .select_related('evaluacion_id_evaluacion')
            .order_by('fecha_ingreso', 'id_calificacion')
        )

        por_asignatura = defaultdict(dict)

        for calificacion in calificaciones:
            evaluacion = calificacion.evaluacion_id_evaluacion

            if evaluacion is None:
                continue

            numero = evaluacion.numero_evaluacion
            asignatura_id = (
                calificacion.asignatura_curso_id_asig_curso_id
            )

            # Si una nota fue actualizada y hay duplicados,
            # se conserva la última según el orden consultado.
            por_asignatura[asignatura_id][numero] = (
                calificacion.valor_nota
            )
            numeros_evaluacion.add(numero)

        numeros_evaluacion = sorted(numeros_evaluacion)

        for asignatura in asignaturas:
            notas = por_asignatura.get(
                asignatura.id_asig_curso, {}
            )

            valores = list(notas.values())
            promedio = (
                round(sum(valores) / len(valores), 1)
                if valores else None
            )

            if promedio is not None:
                promedios.append(
                    sum(valores) / len(valores)
                )

            resumen_notas.append({
                'nombre_asignatura':
                    asignatura.asignatura_id_asignatura.nombre_asignatura,
                'notas': [
                    {'numero': numero, 'valor': notas.get(numero)}
                    for numero in numeros_evaluacion
                ],
                'promedio': promedio
            })

    promedio_general = (
        round(sum(promedios) / len(promedios), 1)
        if promedios else None
    )

    return render(request, 'apoderado_certificados.html', {
        'alumnos': alumnos,
        'alumno_seleccionado': alumno_seleccionado,
        'tipo_certificado': tipo_certificado,
        'resumen_notas': resumen_notas,
        'numeros_evaluacion': numeros_evaluacion,
        'promedio_general': promedio_general,
        'fecha_emision': timezone.localdate(),
        'anio_escolar': timezone.localdate().year,
    })



@require_role([3])
def apoderado_descargar_certificado(request):
    from collections import defaultdict
    from io import BytesIO
    from html import escape

    from django.http import Http404, HttpResponse
    from django.utils import timezone

    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.pagesizes import A4, A3, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        LongTable,
        TableStyle,
        KeepTogether
    )

    from .models import Alumno, AsignaturaCurso, Calificacion

    # ============================================
    # 1. VALIDAR APODERADO Y ESTUDIANTE
    # ============================================

    rut_apoderado = request.session.get('usuario_rut')
    rut_alumno = request.GET.get('alumno', '').strip()
    tipo = request.GET.get('tipo', 'regular').strip()

    if tipo not in ('regular', 'notas'):
        raise Http404('Tipo de certificado inválido.')

    alumno = (
        Alumno.objects
        .filter(
            rut_alumno=rut_alumno,
            usuario_rut_id=rut_apoderado
        )
        .select_related('curso_id_curso')
        .first()
    )

    if alumno is None:
        raise Http404('Estudiante no asociado a este apoderado.')

    # ============================================
    # 2. COLORES INSTITUCIONALES
    # ============================================

    AZUL = colors.HexColor('#17365D')
    AZUL_OSCURO = colors.HexColor('#102A47')
    AZUL_CLARO = colors.HexColor('#EAF2FB')
    NARANJA = colors.HexColor('#F97316')
    NARANJA_CLARO = colors.HexColor('#FFF3E9')
    GRIS = colors.HexColor('#64748B')
    GRIS_CLARO = colors.HexColor('#F8FAFC')
    BORDE = colors.HexColor('#DCE5EF')
    VERDE = colors.HexColor('#15803D')
    ROJO = colors.HexColor('#DC2626')

    fecha_emision = timezone.localdate()
    anio_escolar = fecha_emision.year

    nombre_alumno = escape(str(alumno.nombre_completo))
    rut_estudiante = escape(str(alumno.rut_alumno))
    nombre_curso = escape(
        str(alumno.curso_id_curso.nombre_curso)
    )

    # ============================================
    # 3. CONFIGURAR PDF
    # ============================================

    buffer = BytesIO()

    pagina = landscape(A3) if tipo == 'notas' else A4

    documento = SimpleDocTemplate(
        buffer,
        pagesize=pagina,
        leftMargin=2.1 * cm,
        rightMargin=2.1 * cm,
        topMargin=4.3 * cm,
        bottomMargin=4.0 * cm if tipo == 'regular' else 2.5 * cm,
        title=(
            'Certificado de Calificaciones'
            if tipo == 'notas'
            else 'Certificado de Alumno Regular'
        ),
        author='Sistema de Gestión Escolar - Santa Juliana'
    )

    ancho_pagina, alto_pagina = pagina
    ancho_util = (
        ancho_pagina
        - documento.leftMargin
        - documento.rightMargin
    )

    # ============================================
    # 4. ESTILOS
    # ============================================

    estilos = getSampleStyleSheet()

    estilos.add(ParagraphStyle(
        name='TituloSGE',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=23,
        textColor=AZUL_OSCURO,
        alignment=TA_CENTER,
        spaceAfter=9
    ))

    estilos.add(ParagraphStyle(
        name='SubtituloSGE',
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=GRIS,
        alignment=TA_CENTER,
        spaceAfter=12
    ))

    estilos.add(ParagraphStyle(
        name='TextoSGE',
        fontName='Helvetica',
        fontSize=10.5,
        leading=18,
        textColor=AZUL_OSCURO,
        alignment=TA_LEFT,
        spaceAfter=14
    ))

    estilos.add(ParagraphStyle(
        name='EtiquetaSGE',
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=14,
        textColor=AZUL
    ))

    estilos.add(ParagraphStyle(
        name='ValorSGE',
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=AZUL_OSCURO
    ))

    estilos.add(ParagraphStyle(
        name='SeccionSGE',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=16,
        textColor=AZUL,
        spaceBefore=8,
        spaceAfter=12
    ))

    estilos.add(ParagraphStyle(
        name='CeldaSGE',
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=AZUL_OSCURO
    ))

    estilos.add(ParagraphStyle(
        name='CeldaNegritaSGE',
        parent=estilos['CeldaSGE'],
        fontName='Helvetica-Bold'
    ))

    estilos.add(ParagraphStyle(
        name='CeldaBlancaSGE',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white
    ))

    estilos.add(ParagraphStyle(
        name='NotaSGE',
        fontName='Helvetica',
        fontSize=8.5,
        leading=13,
        textColor=GRIS,
        spaceAfter=8
    ))

    # ============================================
    # 5. ENCABEZADO Y PIE DE PÁGINA
    # ============================================

    def decorar_pagina(canvas, doc):
        canvas.saveState()

        # Franja superior azul
        canvas.setFillColor(AZUL)
        canvas.rect(
            0,
            alto_pagina - 2.75 * cm,
            ancho_pagina,
            2.75 * cm,
            fill=1,
            stroke=0
        )

        # Franja naranja
        canvas.setFillColor(NARANJA)
        canvas.rect(
            0,
            alto_pagina - 2.86 * cm,
            ancho_pagina,
            0.11 * cm,
            fill=1,
            stroke=0
        )

        # Logotipo tipográfico SGE
        canvas.setFillColor(NARANJA)
        canvas.roundRect(
            2.0 * cm,
            alto_pagina - 2.05 * cm,
            1.25 * cm,
            1.05 * cm,
            7,
            fill=1,
            stroke=0
        )

        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawCentredString(
            2.625 * cm,
            alto_pagina - 1.67 * cm,
            'SGE'
        )

        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawString(
            3.6 * cm,
            alto_pagina - 1.36 * cm,
            'LICEO POLIVALENTE SANTA JULIANA'
        )

        canvas.setFont('Helvetica', 9)
        canvas.drawString(
            3.6 * cm,
            alto_pagina - 1.81 * cm,
            'Sistema de Gestión Escolar'
        )

        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawRightString(
            ancho_pagina - 2.0 * cm,
            alto_pagina - 1.48 * cm,
            f'AÑO ESCOLAR {anio_escolar}'
        )

        # Marca de agua discreta
        canvas.saveState()
        canvas.setFillColor(
            colors.HexColor('#F1F5F9')
        )
        canvas.setFont('Helvetica-Bold', 70)
        canvas.translate(
            ancho_pagina / 2,
            alto_pagina / 2
        )
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, 'SGE')
        canvas.restoreState()

        # Pie de página
        canvas.setStrokeColor(BORDE)
        canvas.setLineWidth(0.7)
        canvas.line(
            2 * cm,
            1.65 * cm,
            ancho_pagina - 2 * cm,
            1.65 * cm
        )

        canvas.setFillColor(AZUL)
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(
            2 * cm,
            1.30 * cm,
            'LICEO POLIVALENTE SANTA JULIANA'
        )

        canvas.setFillColor(GRIS)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(
            2 * cm,
            1.02 * cm,
            'Documento generado por el Sistema de Gestión Escolar'
        )

        canvas.drawRightString(
            ancho_pagina - 2 * cm,
            1.30 * cm,
            f'Emitido: {fecha_emision.strftime("%d/%m/%Y")}'
        )

        canvas.drawRightString(
            ancho_pagina - 2 * cm,
            1.02 * cm,
            f'Página {doc.page}'
        )

        # Firma decorativa solo en certificado regular
        if tipo == 'regular' and doc.page == 1:

            firma_x = ancho_pagina - 7.1 * cm
            firma_y = 5.1 * cm

            # Firma gráfica ilustrativa
            canvas.setStrokeColor(AZUL)
            canvas.setLineWidth(1.5)

            trazo = canvas.beginPath()
            trazo.moveTo(firma_x + 0.1 * cm, firma_y)
            trazo.curveTo(
                firma_x + 0.7 * cm, firma_y + 0.8 * cm,
                firma_x + 0.6 * cm, firma_y - 0.4 * cm,
                firma_x + 1.7 * cm, firma_y + 0.5 * cm
            )
            trazo.curveTo(
                firma_x + 2.2 * cm, firma_y + 0.9 * cm,
                firma_x + 1.6 * cm, firma_y - 0.2 * cm,
                firma_x + 3.0 * cm, firma_y + 0.35 * cm
            )
            trazo.curveTo(
                firma_x + 3.5 * cm, firma_y + 0.7 * cm,
                firma_x + 3.7 * cm, firma_y - 0.2 * cm,
                firma_x + 4.4 * cm, firma_y + 0.2 * cm
            )
            canvas.drawPath(trazo)

            canvas.setStrokeColor(GRIS)
            canvas.setLineWidth(0.6)
            canvas.line(
                firma_x - 0.2 * cm,
                firma_y - 0.45 * cm,
                firma_x + 5 * cm,
                firma_y - 0.45 * cm
            )

            canvas.setFillColor(AZUL_OSCURO)
            canvas.setFont('Helvetica-Bold', 9)
            canvas.drawCentredString(
                firma_x + 2.4 * cm,
                firma_y - 0.85 * cm,
                'Dirección del Establecimiento'
            )

            canvas.setFillColor(GRIS)
            canvas.setFont('Helvetica', 7.5)
            canvas.drawCentredString(
                firma_x + 2.4 * cm,
                firma_y - 1.15 * cm,
                'Firma ilustrativa - No autorizada'
            )

        canvas.restoreState()

    # ============================================
    # 6. CONTENIDO COMPARTIDO
    # ============================================

    contenido = []

    titulo = (
        'CERTIFICADO DE CALIFICACIONES'
        if tipo == 'notas'
        else 'CERTIFICADO DE ALUMNO REGULAR'
    )

    contenido.append(
        Paragraph(titulo, estilos['TituloSGE'])
    )

    contenido.append(
        Paragraph(
            f'Período académico {anio_escolar}',
            estilos['SubtituloSGE']
        )
    )

    contenido.append(Spacer(1, 0.35 * cm))

    contenido.append(
        Paragraph(
            'ANTECEDENTES DEL ESTUDIANTE',
            estilos['SeccionSGE']
        )
    )

    datos = [
        [
            Paragraph('Nombre completo:', estilos['EtiquetaSGE']),
            Paragraph(nombre_alumno, estilos['ValorSGE'])
        ],
        [
            Paragraph('R.U.T:', estilos['EtiquetaSGE']),
            Paragraph(rut_estudiante, estilos['ValorSGE'])
        ],
        [
            Paragraph('Curso:', estilos['EtiquetaSGE']),
            Paragraph(nombre_curso, estilos['ValorSGE'])
        ],
        [
            Paragraph('Año escolar:', estilos['EtiquetaSGE']),
            Paragraph(str(anio_escolar), estilos['ValorSGE'])
        ]
    ]

    tabla_datos = Table(
        datos,
        colWidths=[
            ancho_util * 0.30,
            ancho_util * 0.70
        ],
        hAlign='LEFT'
    )

    tabla_datos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRIS_CLARO),
        ('BACKGROUND', (0, 0), (0, -1), AZUL_CLARO),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, BORDE),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDE),
        ('LEFTPADDING', (0, 0), (-1, -1), 13),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    contenido.append(tabla_datos)
    contenido.append(Spacer(1, 0.75 * cm))

    # ============================================
    # 7. CERTIFICADO ALUMNO REGULAR
    # ============================================

    if tipo == 'regular':

        contenido.append(
            Paragraph(
                'CERTIFICACIÓN DE MATRÍCULA',
                estilos['SeccionSGE']
            )
        )

        contenido.append(
            Paragraph(
                'La Dirección del '
                '<b>Liceo Polivalente Santa Juliana</b> '
                'deja constancia de que el estudiante '
                f'<b>{nombre_alumno}</b>, '
                f'R.U.T. <b>{rut_estudiante}</b>, '
                'se encuentra registrado en el '
                'establecimiento educacional, '
                f'en el curso <b>{nombre_curso}</b>, '
                f'correspondiente al año escolar '
                f'<b>{anio_escolar}</b>.',
                estilos['TextoSGE']
            )
        )

        contenido.append(
            Paragraph(
                'El presente documento se emite '
                'a solicitud del apoderado para '
                'los fines que estime pertinentes.',
                estilos['TextoSGE']
            )
        )

        contenido.append(Spacer(1, 0.35 * cm))

        recuadro = Table(
            [[Paragraph(
                '<b>INFORMACIÓN IMPORTANTE</b><br/>'
                'Este certificado ha sido generado '
                'por el Sistema de Gestión Escolar. '
                'Su validez oficial requiere '
                'la autorización del establecimiento.',
                estilos['NotaSGE']
            )]],
            colWidths=[ancho_util]
        )

        recuadro.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NARANJA_CLARO),
            ('LINEBEFORE', (0, 0), (0, 0), 3, NARANJA),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))

        contenido.append(recuadro)

        contenido.append(Spacer(1, 0.45 * cm))

        contenido.append(
            Paragraph(
                f'Santiago, Chile - '
                f'{fecha_emision.strftime("%d/%m/%Y")}',
                estilos['TextoSGE']
            )
        )

    # ============================================
    # 8. CERTIFICADO DE CALIFICACIONES
    # ============================================

    else:

        contenido.append(
            Paragraph(
                'DETALLE DE CALIFICACIONES REGISTRADAS',
                estilos['SeccionSGE']
            )
        )

        asignaturas = list(
            AsignaturaCurso.objects
            .filter(curso_id_curso=alumno.curso_id_curso)
            .select_related('asignatura_id_asignatura')
            .order_by(
                'asignatura_id_asignatura__nombre_asignatura'
            )
        )

        calificaciones = (
            Calificacion.objects
            .filter(
                alumno_rut_alumno=alumno,
                asignatura_curso_id_asig_curso__curso_id_curso=
                    alumno.curso_id_curso
            )
            .select_related('evaluacion_id_evaluacion')
            .order_by('fecha_ingreso', 'id_calificacion')
        )

        notas_por_asignatura = defaultdict(dict)
        numeros = set()

        for calificacion in calificaciones:

            evaluacion = calificacion.evaluacion_id_evaluacion

            if evaluacion is None:
                continue

            if calificacion.valor_nota is None:
                continue

            numero = evaluacion.numero_evaluacion

            asignatura_id = (
                calificacion.asignatura_curso_id_asig_curso_id
            )

            notas_por_asignatura[asignatura_id][numero] = (
                float(calificacion.valor_nota)
            )

            numeros.add(numero)

        numeros = sorted(numeros)

        # Columnas dinámicas
        cabecera = [
            Paragraph('ASIGNATURA', estilos['CeldaBlancaSGE'])
        ]

        for numero in numeros:
            cabecera.append(
                Paragraph(
                    f'NOTA {numero}',
                    estilos['CeldaBlancaSGE']
                )
            )

        cabecera.append(
            Paragraph('PROMEDIO', estilos['CeldaBlancaSGE'])
        )

        filas = [cabecera]
        promedios = []

        for asignatura in asignaturas:

            notas = notas_por_asignatura.get(
                asignatura.id_asig_curso, {}
            )

            valores = list(notas.values())

            promedio = (
                sum(valores) / len(valores)
                if valores else None
            )

            if promedio is not None:
                promedios.append(promedio)

            nombre = escape(
                str(
                    asignatura.asignatura_id_asignatura
                    .nombre_asignatura
                )
            )

            fila = [
                Paragraph(nombre, estilos['CeldaSGE'])
            ]

            for numero in numeros:

                valor = notas.get(numero)

                fila.append(
                    f'{valor:.1f}'
                    if valor is not None
                    else '-'
                )

            fila.append(
                f'{promedio:.1f}'
                if promedio is not None
                else '-'
            )

            filas.append(fila)

        # Promedio general:
        # Cada asignatura con notas tiene el mismo peso.
        promedio_general = (
            sum(promedios) / len(promedios)
            if promedios else None
        )

        filas.append(
            [
                Paragraph(
                    'PROMEDIO GENERAL',
                    estilos['CeldaNegritaSGE']
                )
            ]
            + [''] * len(numeros)
            + [
                f'{promedio_general:.1f}'
                if promedio_general is not None
                else '-'
            ]
        )

        # Adaptar columnas al tamaño de la página
        ancho_asignatura = min(
            8.5 * cm,
            ancho_util * 0.30
        )

        cantidad_columnas = len(numeros) + 1

        ancho_nota = (
            (ancho_util - ancho_asignatura)
            / cantidad_columnas
        )

        tabla_notas = LongTable(
            filas,
            colWidths=(
                [ancho_asignatura]
                + [ancho_nota] * cantidad_columnas
            ),
            repeatRows=1,
            hAlign='LEFT'
        )

        tamano_fuente = (
            8 if len(numeros) <= 12
            else 6 if len(numeros) <= 22
            else 4.5
        )

        tabla_notas.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), AZUL),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),

            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [
                colors.white,
                GRIS_CLARO
            ]),

            ('BACKGROUND', (0, -1), (-1, -1), AZUL_CLARO),

            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),

            ('GRID', (0, 0), (-1, -1), 0.35, BORDE),

            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            ('FONTSIZE', (0, 0), (-1, -1), tamano_fuente),

            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),

            ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),

            ('LINEABOVE', (0, -1), (-1, -1), 1.5, NARANJA)
        ]))

        # Colorear notas insuficientes
        for indice_fila, asignatura in enumerate(
            asignaturas, start=1
        ):

            notas = notas_por_asignatura.get(
                asignatura.id_asig_curso, {}
            )

            for indice_columna, numero in enumerate(
                numeros, start=1
            ):

                valor = notas.get(numero)

                if valor is not None:
                    tabla_notas.setStyle(TableStyle([
                        (
                            'TEXTCOLOR',
                            (indice_columna, indice_fila),
                            (indice_columna, indice_fila),
                            ROJO if valor < 4 else AZUL
                        )
                    ]))

            valores = list(notas.values())

            if valores:
                promedio = sum(valores) / len(valores)

                tabla_notas.setStyle(TableStyle([
                    (
                        'TEXTCOLOR',
                        (-1, indice_fila),
                        (-1, indice_fila),
                        ROJO if promedio < 4 else VERDE
                    ),
                    (
                        'FONTNAME',
                        (-1, indice_fila),
                        (-1, indice_fila),
                        'Helvetica-Bold'
                    )
                ]))

        if promedio_general is not None:
            tabla_notas.setStyle(TableStyle([
                (
                    'TEXTCOLOR',
                    (-1, -1),
                    (-1, -1),
                    ROJO if promedio_general < 4 else VERDE
                )
            ]))

        contenido.append(tabla_notas)
        contenido.append(Spacer(1, 0.65 * cm))

        # Resumen visual del rendimiento
        total_asignaturas = len(asignaturas)
        asignaturas_con_notas = len(promedios)

        resumen = [
            [
                Paragraph(
                    '<b>ASIGNATURAS</b>',
                    estilos['EtiquetaSGE']
                ),
                Paragraph(
                    '<b>CON CALIFICACIONES</b>',
                    estilos['EtiquetaSGE']
                ),
                Paragraph(
                    '<b>PROMEDIO GENERAL</b>',
                    estilos['EtiquetaSGE']
                )
            ],
            [
                str(total_asignaturas),
                str(asignaturas_con_notas),
                (
                    f'{promedio_general:.1f}'
                    if promedio_general is not None
                    else '-'
                )
            ]
        ]

        tabla_resumen = Table(
            resumen,
            colWidths=[ancho_util / 3] * 3
        )

        tabla_resumen.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), AZUL_CLARO),
            ('BOX', (0, 0), (-1, -1), 0.7, BORDE),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, BORDE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 17),
            ('TEXTCOLOR', (0, 1), (-1, 1), AZUL),
            ('TOPPADDING', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 11)
        ]))

        contenido.append(KeepTogether([
            tabla_resumen,
            Spacer(1, 0.45 * cm),
            Paragraph(
                'El promedio general corresponde al promedio '
                'de las asignaturas que tienen calificaciones '
                'registradas. Las asignaturas sin notas no '
                'participan en este cálculo.',
                estilos['NotaSGE']
            ),
            Paragraph(
                'Las calificaciones reflejan los registros '
                'disponibles en el sistema al momento '
                'de generar el certificado.',
                estilos['NotaSGE']
            )
        ]))

        contenido.append(Spacer(1, 0.25 * cm))

        contenido.append(
            Paragraph(
                'Documento informativo generado por SGE. '
                'Su validez oficial requiere autorización '
                'del establecimiento.',
                estilos['NotaSGE']
            )
        )

    # ============================================
    # 9. GENERAR PDF
    # ============================================

    documento.build(
        contenido,
        onFirstPage=decorar_pagina,
        onLaterPages=decorar_pagina
    )

    pdf = buffer.getvalue()
    buffer.close()

    nombre_archivo = (
        f'certificado_{tipo}_{alumno.rut_alumno}.pdf'
    )

    respuesta = HttpResponse(
        pdf,
        content_type='application/pdf'
    )

    respuesta['Content-Disposition'] = (
        f'attachment; filename="{nombre_archivo}"'
    )

    return respuesta



@require_role([2])
def profesor_inicio(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    # Permitimos el acceso si es profesor (rol 2 o 3) o administrador (rol 1)
    rol = request.session.get('rol_id')
    if rol not in [1, 2, 3]:
        messages.error(request, 'No tienes permisos para acceder a este portal.')
        return redirect('login')
        
    # El resto de tu lógica de inicio de profesor...
    return render(request, 'profesor_inicio.html')

    from django.db.models import Count 
    from django.utils import timezone 
    from .models import Calificacion

    from .models import (
        Curso,
        Alumno,
        RegistroAsistencia,
        Evaluacion,
        SolicitudInsumo,
        TicketSoporte
    )

    hoy = timezone.localdate()
    rut_profesor = request.session.get('usuario_rut')

    # 1. Todos los cursos disponibles del colegio
    total_cursos = Curso.objects.count()

    # 2. Todos los alumnos registrados
    total_alumnos = Alumno.objects.count()

    # 3. Asistencia registrada hoy
    # Una asistencia diaria por alumno, aunque existan
    # registros asociados a distintas asignaturas.
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

    # 5. Incidencias realizadas por el profesor
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




import json
from decimal import Decimal, InvalidOperation
from django.db import transaction, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from sistema.models import Curso, Alumno, AsignaturaCurso, Evaluacion, Calificacion




@require_role([2])
@require_http_methods(["GET", "POST"])
def profesor_notas(request):
    import json
    from decimal import Decimal, InvalidOperation

    from django.db import connection, transaction
    from django.db.models import Q
    from django.http import JsonResponse
    from django.shortcuts import render
    from django.utils import timezone

    from .models import (
        Alumno,
        Curso,
        AsignaturaCurso,
        Evaluacion,
        Calificacion,
    )

    rut_profesor = request.session.get("usuario_rut")

    if not rut_profesor:
        return JsonResponse({
            "ok": False,
            "error": "La sesión del profesor no es válida."
        }, status=403)

    # ==========================================
    # 1. PERMISOS DEL PROFESOR
    # ==========================================

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

    # ==========================================
    # 2. GUARDAR NOTAS Y EVALUACIONES
    # ==========================================

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

        # ==========================================
        # 3. VALIDAR CALIFICACIONES
        # ==========================================

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

        # ==========================================
        # 4. GUARDAR CAMBIOS EN MYSQL
        # ==========================================

        try:
            with transaction.atomic():

                # Bloqueo por asignatura.
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

                # Crear columnas nuevas.
                for numero in columnas:

                    if numero not in evaluaciones_existentes:

                        evaluacion = Evaluacion.objects.create(
                            asignatura_curso_id_asig_curso_id=relacion_id,
                            numero_evaluacion=numero
                        )

                        evaluaciones_existentes[numero] = evaluacion

                        cambios += 1
                        evaluaciones_creadas += 1

                # Eliminar columnas que ya no existen.
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

                # Obtener notas existentes.
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

                # Crear o modificar notas.
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

                # Eliminar notas que quedaron vacías.
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

        # ==========================================
        # 5. RESPUESTA SEGÚN LOS CAMBIOS
        # ==========================================

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

    # ==========================================
    # 6. CURSOS DE JEFATURA
    # ==========================================

    cursos_jefatura = list(
        Curso.objects.filter(
            usuario_rut_id=rut_profesor
        ).order_by("nombre_curso")
    )

    # ==========================================
    # 7. ASIGNATURAS PROPIAS
    # ==========================================

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

    # ==========================================
    # 8. CURSOS Y ASIGNATURAS DISPONIBLES
    # ==========================================

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

    # ==========================================
    # 9. SELECCIÓN DEL CURSO
    # ==========================================

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

    # ==========================================
    # 10. SELECCIÓN DE ASIGNATURA
    # ==========================================

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

        # ==========================================
        # 11. RECUPERAR EVALUACIONES DE MYSQL
        # ==========================================

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

                # CORRECCIÓN:
                # Respetar exactamente las evaluaciones
                # que se encuentran guardadas en MySQL.
                columnas = list(range(1, max_numero + 1))

            else:

                # Asignatura nueva, sin evaluaciones.
                columnas = [1, 2, 3]

            numeros = {
                evaluacion.id_evaluacion: (
                    evaluacion.numero_evaluacion
                )
                for evaluacion in evaluaciones
            }

            # ==========================================
            # 12. RECUPERAR NOTAS GUARDADAS
            # ==========================================

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

    # ==========================================
    # 13. ENVIAR INFORMACIÓN AL HTML
    # ==========================================

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
    import json
    from datetime import date

    from django.db import transaction
    from django.db.models import Q, Max
    from django.http import JsonResponse
    from django.shortcuts import render
    from django.utils import timezone
    from django.contrib import messages

    from .models import (
        Curso,
        Alumno,
        AsignaturaCurso,
        RegistroAsistencia,
    )

    rut_profesor = request.session.get("usuario_rut")

    if not rut_profesor:
        return JsonResponse({
            "ok": False,
            "error": "Sesión inválida."
        }, status=403)

    hoy = timezone.localdate()

    # ==========================================
    # 1. PERMISOS
    # ==========================================

    relaciones_permitidas = (
        AsignaturaCurso.objects.filter(
            Q(usuario_rut_id=rut_profesor)
            | Q(curso_id_curso__usuario_rut_id=rut_profesor)
        ).distinct()
    )

    # ==========================================
    # 2. GUARDAR ASISTENCIA
    # ==========================================

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

            # Verificar permisos de la relación.
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

            # Alumnos del curso.
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

        # ==========================================
        # 3. TRANSACCIÓN MYSQL
        # ==========================================

        try:
            with transaction.atomic():

                # Bloqueo del curso para evitar que
                # dos profesores guarden simultáneamente
                # la asistencia del mismo curso.
                Curso.objects.select_for_update().get(
                    id_curso=curso_id
                )

                # La asistencia es por alumno y fecha.
                # Se revisan todas las asignaturas
                # del curso, no solamente la elegida.
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

                # Crear o actualizar asistencia.
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

    # ==========================================
    # 4. CURSOS DE JEFATURA
    # ==========================================

    cursos_jefatura = list(
        Curso.objects.filter(
            usuario_rut_id=rut_profesor
        ).order_by("nombre_curso")
    )

    # ==========================================
    # 5. ASIGNATURAS PROPIAS
    # ==========================================

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

    # ==========================================
    # 6. ASIGNATURAS PERMITIDAS POR CURSO
    # ==========================================

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

    # ==========================================
    # 7. FILTROS GET
    # ==========================================

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

    # Curso inicial.
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

    # ==========================================
    # 8. SELECCIONAR ASIGNATURA
    # ==========================================

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

        # ==========================================
        # 9. CARGAR ALUMNOS Y ASISTENCIA
        # ==========================================

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

                # Se conserva el registro más reciente.
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

    # ==========================================
    # 10. RENDERIZAR HTML
    # ==========================================

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
    from datetime import date as dt_date
    from django.shortcuts import render as dj_render, redirect as dj_redirect
    from django.contrib import messages as dj_messages
    from django.db.models import Max as dj_Max
    from .models import SolicitudInsumo as Mod_Solicitud, TicketSoporte as Mod_Ticket

    if 'usuario_rut' not in request.session:
        return dj_redirect('login')
        
    if request.method == 'POST':
        tipo = request.POST.get('tipo') or request.POST.get('tipo_incidencia') or ''
        descripcion = request.POST.get('descripcion', '')
        prioridad = request.POST.get('prioridad', 'Media')
        rut_usuario = request.session.get('usuario_rut')
        fecha = request.POST.get('fecha') or dt_date.today()

        es_aseo = tipo in ['material', 'reposicion', 'Solicitud de Material', 'Solicitud de Reposición']

        if es_aseo:
            res = Mod_Solicitud.objects.aggregate(max_val=dj_Max('id_solicitud'))
            nuevo_id = (res.get('max_val') or 0) + 1

            Mod_Solicitud.objects.create(
                id_solicitud=nuevo_id,
                fecha=fecha,
                estado_solicitud='Pendiente',
                usuario_rut_id=rut_usuario,
                descripcion=descripcion,
                tipo_solicitud='Solicitud de Material' if tipo == 'material' else tipo
            )
            dj_messages.success(request, '¡Solicitud de aseo enviada con éxito!')
            return dj_redirect('profesor_gestion_incidencias')

        else:
            res = Mod_Ticket.objects.aggregate(max_val=dj_Max('id_ticket'))
            nuevo_id_ticket = (res.get('max_val') or 0) + 1

            Mod_Ticket.objects.create(
                id_ticket=nuevo_id_ticket,
                fecha_reporte=fecha,
                prioridad=prioridad,
                estado_ticket='Pendiente',
                usuario_rut_id=rut_usuario,
                descripcion=descripcion,
                tipo_incidencia=tipo,
                equipo_ti_codigo_inventario_id='EXT-001'
            )
            dj_messages.success(request, '¡Incidencia de TI registrada con éxito!')
            return dj_redirect('profesor_gestion_incidencias')

    return dj_render(request, 'profesor_agregar_incidencia.html')

    from datetime import date
    from django.contrib import messages
    from django.db import transaction
    from django.db.models import Max
    from django.shortcuts import redirect, render
    from django.utils import timezone

    from .models import (
        Usuario,
        EquipoTi,
        SolicitudInsumo,
        TicketSoporte
    )

    tipos = {
        'material': ('insumo', 'Solicitud de Material'),
        'reposicion': ('insumo', 'Solicitud de Reposición'),
        'equipo': ('soporte', 'Problema con Equipo'),
        'mantenimiento': ('soporte', 'Mantenimiento'),
    }

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
        fecha_texto = request.POST.get('fecha', '').strip()
        tipo = request.POST.get('tipo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        codigo_equipo = request.POST.get('equipo', '').strip()

        try:
            fecha = date.fromisoformat(fecha_texto)
        except ValueError:
            messages.error(request, 'La fecha ingresada no es válida.')
            return redirect('profesor_agregar_incidencia')

        if tipo not in tipos:
            messages.error(request, 'Selecciona un tipo de incidencia válido.')
            return redirect('profesor_agregar_incidencia')

        if not descripcion:
            messages.error(request, 'Debes ingresar una descripción.')
            return redirect('profesor_agregar_incidencia')

        rut_profesor = request.session.get('usuario_rut')

        if not rut_profesor or not Usuario.objects.filter(
            rut=rut_profesor
        ).exists():
            messages.error(request, 'No se encontró el usuario de la sesión.')
            return redirect('profesor_agregar_incidencia')

        destino, nombre_tipo = tipos[tipo]

        equipo = None

        if destino == 'soporte':
            if not codigo_equipo:
                messages.error(
                    request,
                    'Debes seleccionar el equipo involucrado.'
                )
                return redirect('profesor_agregar_incidencia')

            equipo = EquipoTi.objects.filter(
                codigo_inventario=codigo_equipo
            ).first()

            if equipo is None:
                messages.error(
                    request,
                    'El equipo seleccionado no existe.'
                )
                return redirect('profesor_agregar_incidencia')

        try:
            with transaction.atomic():
                if destino == 'insumo':
                    ultimo_id = (
                        SolicitudInsumo.objects.aggregate(
                            max_id=Max('id_solicitud')
                        )['max_id'] or 0
                    )

                    SolicitudInsumo.objects.create(
                        id_solicitud=ultimo_id + 1,
                        fecha=fecha,
                        estado_solicitud='Pendiente',
                        usuario_rut_id=rut_profesor,
                        descripcion=descripcion,
                        tipo_solicitud=nombre_tipo
                    )

                else:
                    ultimo_id = (
                        TicketSoporte.objects.aggregate(
                            max_id=Max('id_ticket')
                        )['max_id'] or 0
                    )

                    TicketSoporte.objects.create(
                        id_ticket=ultimo_id + 1,
                        fecha_reporte=fecha,
                        prioridad='Media',
                        usuario_rut_id=rut_profesor,
                        equipo_ti_codigo_inventario=equipo,
                        descripcion=descripcion,
                        tipo_incidencia=nombre_tipo
                    )

        except Exception:
            messages.error(
                request,
                'No se pudo guardar la incidencia. Revisa la base de datos.'
            )
            return redirect('profesor_agregar_incidencia')

        messages.success(
            request,
            f'{nombre_tipo} registrada correctamente.'
        )

        return redirect('profesor_agregar_incidencia')

    return render(request, 'profesor_agregar_incidencia.html', {
        'equipos': equipos,
        'fecha_actual': timezone.localdate().isoformat()
    })

@require_role([2]) # Rol 2: Profesor
def profesor_gestion_incidencias(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    rut_profesor = request.session.get('usuario_rut')
    
    # 1. Incidencias de TI usando el modelo TicketSoporte
    incidencias_ti = TicketSoporte.objects.filter(usuario_rut_id=rut_profesor).order_by('-id_ticket')
    
    # 2. Solicitudes de Aseo usando el modelo SolicitudInsumo
    solicitudes_aseo = SolicitudInsumo.objects.filter(usuario_rut=rut_profesor).order_by('-id_solicitud')
    
    context = {
        'incidencias_ti': incidencias_ti,
        'solicitudes_aseo': solicitudes_aseo,
    }
    return render(request, 'profesor_gestion_incidencias.html', context)

@require_role([2]) # Rol 2: Profesor
def profesor_detalle_incidencia(request, pk):
    rut_profesor = request.session.get('usuario_rut')
    ticket = get_object_or_404(TicketSoporte, pk=pk, usuario_rut__rut=rut_profesor)
    
    context = {
        'ticket': ticket
    }
    return render(request, 'profesor_detalle_incidencia.html', context)

@require_role([2])
def profesor_alumnos(request):
    from django.db.models import Avg, OuterRef, Subquery
    from .models import Calificacion

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
    from django.db.models import Avg, Count
    from .models import Calificacion, RegistroAsistencia

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
    # Promedio de todas las calificaciones registradas, sin inventar semestres.
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
        .order_by('-fecha', '-id_asistencia')[:15]
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

# Vistas para el portal de Administrador

@require_role([1, 4])
def admin_inicio(request):
    return render(request, 'admin_inicio.html')

from django.core.paginator import Paginator
from django.db.models import Q

@require_role([1, 4])
def admin_gestion_usuarios(request):
    # 1. Extraemos todos los usuarios y traemos los datos de su rol asociado
    lista_usuarios = Usuario.objects.select_related('rol_id_rol').all().order_by('apellido_paterno', 'nombre')
    
    # 2. Capturamos lo que venga del buscador ('q') y del select ('rol')
    query = request.GET.get('q', '').strip()
    rol_filtro = request.GET.get('rol', '').strip()

    # 3. Búsqueda inteligente multi-palabra por nombre, apellidos, correo o RUT
    if query:
        palabras = query.split()
        for palabra in palabras:
            lista_usuarios = lista_usuarios.filter(
                Q(nombre__icontains=palabra) |
                Q(apellido_paterno__icontains=palabra) |
                Q(apellido_materno__icontains=palabra) |
                Q(correo__icontains=palabra) |
                Q(rut__icontains=palabra)
            )

    # 4. Si seleccionaron un rol en el desplegable, filtramos por ese ID de rol
    if rol_filtro:
        lista_usuarios = lista_usuarios.filter(rol_id_rol_id=rol_filtro)

    # 5. Traemos todos los roles de la BD para llenar el <select> del HTML
    roles = Rol.objects.all()

    # 6. Aplicamos la paginación sobre la lista ya filtrada (10 usuarios por página)
    paginator = Paginator(lista_usuarios, 10)
    page_number = request.GET.get('page')
    usuarios = paginator.get_page(page_number)

    # Empaquetamos todo en el contexto
    context = {
        'usuarios': usuarios,
        'roles': roles,
        'query': query,
        'rol_filtro': rol_filtro,
    }
    return render(request, 'admin_gestion_usuarios.html', context)

@require_role([1, 4])
def admin_crear_usuario(request):
    # 1. Obtenemos siempre los roles de la base de datos para pasarlos al formulario
    roles = Rol.objects.all()

    if request.method == 'POST':
        # Capturamos todos los datos del HTML
        rut_form = request.POST.get('rut', '').strip()
        rol_id = request.POST.get('rol_id_rol')
        nombre_form = request.POST.get('nombre', '').strip()
        correo_form = request.POST.get('correo', '').strip()
        ap_paterno_form = request.POST.get('apellido_paterno', '').strip()
        ap_materno_form = request.POST.get('apellido_materno', '').strip()
        telefono_form = request.POST.get('telefono', '').strip()
        direccion_form = request.POST.get('direccion', '').strip()
        fecha_nac_form = request.POST.get('fecha_nacimiento')

        # 2. Validación de RUT mediante algoritmo Módulo 11
        if not validar_rut(rut_form):
            messages.error(request, 'El RUN ingresado no es válido. Verifique los dígitos e intente nuevamente.')
            return render(request, 'admin_crear_usuario.html', {'roles': roles})

        # 3. Normalización y formateo con puntos (ej: 19.572.314-1)
        rut_limpio = rut_form.replace(".", "").replace("-", "").strip().upper()
        if len(rut_limpio) >= 2:
            cuerpo = rut_limpio[:-1]
            dv = rut_limpio[-1]
            try:
                cuerpo_con_puntos = f"{int(cuerpo):,}".replace(",", ".")
                rut_estandar = f"{cuerpo_con_puntos}-{dv}"
            except ValueError:
                rut_estandar = rut_form
        else:
            rut_estandar = rut_form

        # 4. Comprobar si el RUT con formato tradicional ya existe en la BD
        if Usuario.objects.filter(rut=rut_estandar).exists():
            messages.error(request, f'El RUT {rut_estandar} ya se encuentra registrado en el sistema.')
            return render(request, 'admin_crear_usuario.html', {'roles': roles})

        # 5. Comprobar si el correo ya existe
        if correo_form and Usuario.objects.filter(correo=correo_form.lower()).exists():
            messages.error(request, f'El correo {correo_form} ya pertenece a otro usuario.')
            return render(request, 'admin_crear_usuario.html', {'roles': roles})

        # Contraseña inicial cifrada usando los dígitos del RUT limpio
        password_defecto = make_password(rut_limpio)

        # 6. Creación y persistencia del usuario en la base de datos
        try:
            Usuario.objects.create(
                rut=rut_estandar,
                password_hash=password_defecto,
                rol_id_rol_id=rol_id,
                nombre=nombre_form,
                correo=correo_form.lower() if correo_form else None,
                apellido_paterno=ap_paterno_form,
                apellido_materno=ap_materno_form,
                telefono=telefono_form,
                direccion=direccion_form,
                fecha_nacimiento=fecha_nac_form if fecha_nac_form else None,
                cambiar_password=True
            )

            messages.success(request, 'Usuario creado correctamente con todos sus datos.')
            return redirect('admin_gestion_usuarios')

        except IntegrityError:
            messages.error(request, 'Error de integridad: El usuario o un dato único ya existe en el sistema.')
            return render(request, 'admin_crear_usuario.html', {'roles': roles})

    # Si entra por primera vez (GET), enviamos los roles al HTML
    return render(request, 'admin_crear_usuario.html', {'roles': roles})

@require_role([1, 4])
def admin_editar_usuario(request, rut):
    # 1. Normalizamos el RUT recibido en la URL para buscarlo en la BD (ej: 19.572.314-1)
    rut_limpio = str(rut).replace(".", "").replace("-", "").strip().upper()
    if len(rut_limpio) >= 2:
        cuerpo = rut_limpio[:-1]
        dv = rut_limpio[-1]
        try:
            cuerpo_con_puntos = f"{int(cuerpo):,}".replace(",", ".")
            rut_estandar = f"{cuerpo_con_puntos}-{dv}"
        except ValueError:
            rut_estandar = rut
    else:
        rut_estandar = rut

    # Obtenemos el usuario y la lista de los 5 roles de la base de datos
    usuario = get_object_or_404(Usuario, rut=rut_estandar)
    roles = Rol.objects.all().order_by('id_rol')

    if request.method == 'POST':
        # Capturamos los datos editables del formulario
        nombre_form = request.POST.get('nombre', '').strip()
        ap_paterno_form = request.POST.get('apellido_paterno', '').strip()
        ap_materno_form = request.POST.get('apellido_materno', '').strip()
        correo_form = request.POST.get('correo', '').strip()
        rol_id = request.POST.get('rol_id_rol')
        telefono_form = request.POST.get('telefono', '').strip()
        direccion_form = request.POST.get('direccion', '').strip()
        fecha_nac_form = request.POST.get('fecha_nacimiento')

        # 2. Validar que el correo no pertenezca a OTRO usuario
        if correo_form:
            correo_lower = correo_form.lower()
            existe_correo = Usuario.objects.filter(correo=correo_lower).exclude(rut=usuario.rut).exists()
            if existe_correo:
                messages.error(request, f'El correo {correo_form} ya pertenece a otro usuario registrado.')
                return render(request, 'admin_editar_usuario.html', {'usuario': usuario, 'roles': roles})

        try:
            # 3. Actualizamos los campos
            usuario.nombre = nombre_form
            usuario.apellido_paterno = ap_paterno_form
            usuario.apellido_materno = ap_materno_form
            usuario.correo = correo_lower if correo_form else None
            usuario.rol_id_rol_id = rol_id
            usuario.telefono = telefono_form
            usuario.direccion = direccion_form
            usuario.fecha_nacimiento = fecha_nac_form if fecha_nac_form else None
            usuario.activo = 1 if 'activo' in request.POST else 0
            usuario.save()

            messages.success(request, f'Usuario {usuario.rut} actualizado correctamente.')
            return redirect('admin_gestion_usuarios')

        except IntegrityError:
            messages.error(request, 'Error de integridad al intentar actualizar los datos.')
            return render(request, 'admin_editar_usuario.html', {'usuario': usuario, 'roles': roles})

    return render(request, 'admin_editar_usuario.html', {'usuario': usuario, 'roles': roles})


from django.db import transaction, IntegrityError
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from .models import Usuario, SolicitudInsumo, TicketSoporte, AsignaturaCurso, DetalleInsumo, Curso, Evaluacion

@require_role([1, 4])
def admin_eliminar_usuario(request, rut):
    usuario = get_object_or_404(Usuario, rut=rut)
    rut_actual = request.session.get('usuario_rut')

    if usuario.rut == rut_actual:
        messages.error(request, 'No puedes eliminar tu propia cuenta activa.')
        return redirect('admin_gestion_usuarios')

    try:
        with transaction.atomic():
            # 1. Eliminar toda la carga académica asociada al profesor
            AsignaturaCurso.objects.filter(usuario_rut=usuario).delete()

            # 2. Reasignar jefaturas de curso al admin actual si las tuviera
            Curso.objects.filter(usuario_rut=usuario).update(usuario_rut_id=rut_actual)

            # 3. Eliminar solicitudes de insumos y tickets de soporte asociados
            solicitudes_ids = SolicitudInsumo.objects.filter(usuario_rut=usuario).values_list('id_solicitud', flat=True)
            DetalleInsumo.objects.filter(solicitud_insumo_id_solicitud__in=solicitudes_ids).delete()
            SolicitudInsumo.objects.filter(usuario_rut=usuario).delete()
            TicketSoporte.objects.filter(usuario_rut=usuario).delete()

            # 4. Borrar al usuario de forma definitiva
            usuario.delete()
            messages.success(request, f'Usuario {usuario.nombre} {usuario.apellido_paterno} eliminado correctamente.')
    except IntegrityError:
        # Si por alguna razón queda amarrado a una nota histórica con alumnos, lo dejamos inactivo
        usuario.activo = 0
        usuario.save()
        messages.warning(
            request,
            f'El usuario tiene registros históricos inalterables. Su cuenta fue cambiada a estado Inactivo.'
        )

    return redirect('admin_gestion_usuarios')

from django.core.paginator import Paginator
from django.db.models import Q

@require_role([1, 4])
def admin_alumnos(request):
    # 1. Obtenemos los alumnos con su curso
    alumnos_qs = Alumno.objects.select_related(
        'curso_id_curso'
    ).order_by('nombre_completo')

    cursos = Curso.objects.all().order_by('id_curso')

    # 2. Capturamos los filtros de la URL
    query = request.GET.get('q', '').strip()
    curso_seleccionado = request.GET.get('curso', '').strip()

    # 3. Búsqueda inteligente multi-palabra por nombre o RUT
    if query:
        palabras = query.split()
        for palabra in palabras:
            alumnos_qs = alumnos_qs.filter(
                Q(nombre_completo__icontains=palabra) |
                Q(rut_alumno__icontains=palabra)
            )

    # 4. Filtro por curso seleccionado
    if curso_seleccionado:
        alumnos_qs = alumnos_qs.filter(
            curso_id_curso_id=curso_seleccionado
        )

    # 5. Paginación formal: 10 alumnos por página
    paginator = Paginator(alumnos_qs, 10)
    page_number = request.GET.get('page')
    alumnos_paginados = paginator.get_page(page_number)

    # 6. Cruzamos de forma segura el apoderado para cada alumno de la página actual
    lista_alumnos_procesada = []
    for alumno in alumnos_paginados:
        alumno.nombre_apoderado_str = None
        
        # Verificamos si tiene un valor en usuario_rut (sea objeto o string de RUT)
        if hasattr(alumno, 'usuario_rut') and alumno.usuario_rut:
            if isinstance(alumno.usuario_rut, Usuario):
                alumno.nombre_apoderado_str = f"{alumno.usuario_rut.nombre} {alumno.usuario_rut.apellido_paterno}"
            else:
                # Si está guardado como RUT/string en la BD, lo buscamos en la tabla Usuario
                apo = Usuario.objects.filter(rut=str(alumno.usuario_rut)).first()
                if apo:
                    alumno.nombre_apoderado_str = f"{apo.nombre} {apo.apellido_paterno}"
                    
        lista_alumnos_procesada.append(alumno)

    alumnos_paginados.object_list = lista_alumnos_procesada

    context = {
        'alumnos': alumnos_paginados,
        'cursos': cursos,
        'curso_seleccionado': curso_seleccionado,
        'query': query,
    }

    return render(request, 'admin_alumnos.html', context)
@require_role([1])
def admin_crear_alumno(request):

    cursos = Curso.objects.all().order_by('id_curso')

    apoderados = Usuario.objects.filter(
        rol_id_rol_id=3
    ).order_by('nombre', 'apellido_paterno')

    context = {
        'cursos': cursos,
        'apoderados': apoderados,
    }

    if request.method == 'POST':

        rut_form = request.POST.get('rut_alumno', '').strip()
        nombre = request.POST.get('nombre_completo', '').strip()
        curso_id = request.POST.get('curso', '').strip()
        estado = request.POST.get('estado_matricula', '').strip()
        apoderado_rut = request.POST.get('apoderado', '').strip()

        context['datos'] = request.POST

        # Validar RUT
        if not validar_rut(rut_form):
            messages.error(request, 'El RUT del alumno no es válido.')
            return render(request, 'admin_crear_alumno.html', context)

        # Normalizar RUT al formato usado por el sistema
        rut_limpio = rut_form.replace('.', '').replace('-', '').upper()
        cuerpo = rut_limpio[:-1]
        dv = rut_limpio[-1]

        rut_estandar = f"{int(cuerpo):,}".replace(',', '.') + '-' + dv

        # Validar duplicados
        if Alumno.objects.filter(rut_alumno=rut_estandar).exists():
            messages.error(request, 'Este alumno ya está registrado.')
            return render(request, 'admin_crear_alumno.html', context)

        if not nombre:
            messages.error(request, 'Debes ingresar el nombre completo.')
            return render(request, 'admin_crear_alumno.html', context)

        # Validar curso existente
        curso = Curso.objects.filter(id_curso=curso_id).first() if curso_id.isdigit() else None

        if curso is None:
            messages.error(request, 'Debes seleccionar un curso válido.')
            return render(request, 'admin_crear_alumno.html', context)

        if estado not in ['Activo', 'Inactivo']:
            messages.error(request, 'Selecciona un estado de matrícula válido.')
            return render(request, 'admin_crear_alumno.html', context)

        # Validar que sí o sí hayan seleccionado un apoderado (MySQL no permite NULL en USUARIO_rut)
        if not apoderado_rut:
            messages.error(request, 'Debes seleccionar un apoderado para el alumno.')
            return render(request, 'admin_crear_alumno.html', context)

        apoderado = Usuario.objects.filter(
            rut=apoderado_rut,
            rol_id_rol_id=3
        ).first()

        if apoderado is None:
            messages.error(request, 'El apoderado seleccionado no es válido.')
            return render(request, 'admin_crear_alumno.html', context)

        try:
            with transaction.atomic():
                Alumno.objects.create(
                    rut_alumno=rut_estandar,
                    nombre_completo=nombre,
                    curso_id_curso=curso,
                    estado_matricula=estado,
                    usuario_rut=apoderado
                )

            messages.success(
                request,
                f'El alumno {nombre} fue registrado correctamente.'
            )

            return redirect('admin_alumnos')

        except IntegrityError:
            messages.error(
                request,
                'No se pudo registrar el alumno. Verifica que sus datos no estén duplicados.'
            )

    return render(request, 'admin_crear_alumno.html', context)

@require_role([1])
def admin_editar_alumno(request, rut):

    # Buscar el alumno mediante su RUT
    alumno = get_object_or_404(
        Alumno.objects.select_related(
            'curso_id_curso',
            'usuario_rut'
        ),
        rut_alumno=rut
    )

    # Obtener cursos y apoderados desde MySQL
    cursos = Curso.objects.all().order_by('id_curso')

    apoderados = Usuario.objects.filter(
        rol_id_rol_id=3
    ).order_by('nombre', 'apellido_paterno')

    context = {
        'alumno': alumno,
        'cursos': cursos,
        'apoderados': apoderados
    }

    if request.method == 'POST':

        nombre = request.POST.get(
            'nombre_completo', ''
        ).strip()

        curso_id = request.POST.get(
            'curso', ''
        ).strip()

        estado = request.POST.get(
            'estado_matricula', ''
        ).strip()

        apoderado_rut = request.POST.get(
            'apoderado', ''
        ).strip()

        # Conservar datos ingresados si hay errores
        context['datos'] = request.POST

        # Validar nombre
        if not nombre:
            messages.error(
                request,
                'El nombre completo es obligatorio.'
            )
            return render(
                request,
                'admin_editar_alumno.html',
                context
            )

        # Validar curso
        curso = (
            Curso.objects.filter(
                id_curso=curso_id
            ).first()
            if curso_id.isdigit()
            else None
        )

        if curso is None:
            messages.error(
                request,
                'Selecciona un curso válido.'
            )
            return render(
                request,
                'admin_editar_alumno.html',
                context
            )

        # Validar estado
        if estado not in ['Activo', 'Inactivo']:
            messages.error(
                request,
                'Selecciona un estado válido.'
            )
            return render(
                request,
                'admin_editar_alumno.html',
                context
            )

        # Validar apoderado
        apoderado = None

        if apoderado_rut:
            apoderado = Usuario.objects.filter(
                rut=apoderado_rut,
                rol_id_rol_id=3
            ).first()

            if apoderado is None:
                messages.error(
                    request,
                    'El apoderado seleccionado no es válido.'
                )
                return render(
                    request,
                    'admin_editar_alumno.html',
                    context
                )

        # MySQL exige que el alumno tenga apoderado
        # No permitimos guardar NULL en USUARIO_rut
        if apoderado is None:
            messages.error(
                request,
                'Debes seleccionar un apoderado para el alumno.'
            )
            return render(
                request,
                'admin_editar_alumno.html',
                context
            )

        try:
            # Actualizar campos
            alumno.nombre_completo = nombre
            alumno.curso_id_curso = curso
            alumno.estado_matricula = estado
            alumno.usuario_rut = apoderado

            # Guardar cambios en MySQL
            alumno.save(
                update_fields=[
                    'nombre_completo',
                    'curso_id_curso',
                    'estado_matricula',
                    'usuario_rut'
                ]
            )

            messages.success(
                request,
                f'El alumno {nombre} fue actualizado correctamente.'
            )

            return redirect('admin_alumnos')

        except IntegrityError:
            messages.error(
                request,
                'No se pudo actualizar el alumno. Revisa los datos ingresados.'
            )

    return render(
        request,
        'admin_editar_alumno.html',
        context
    )


from django.core.paginator import Paginator
from django.db.models import Q
from .models import TicketSoporte, EquipoTi, Usuario, Rol  # Importamos TicketSoporte en lugar de Incidencia

from django.core.paginator import Paginator
from django.db.models import Q

@require_role([1, 4])
def admin_gestion_incidencias(request):
    # 1. Consultamos usando TicketSoporte y ordenamos por fecha de reporte descendente
    lista_incidencias = TicketSoporte.objects.all().order_by('-fecha_reporte', '-id_ticket')
    
    # 2. Capturamos los filtros de la URL (búsqueda, estado y prioridad)
    query = request.GET.get('q', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    prioridad_filtro = request.GET.get('prioridad', '').strip()

    # 3. Aplicamos los filtros si el usuario los seleccionó
    if query:
        lista_incidencias = lista_incidencias.filter(
            Q(equipo_ti_codigo_inventario__ubicacion__icontains=query) | 
            Q(equipo_ti_codigo_inventario__codigo_inventario__icontains=query) | 
            Q(id_ticket__icontains=query)
        )
        
    if estado_filtro and estado_filtro != 'Todos':
        lista_incidencias = lista_incidencias.filter(estado_ticket=estado_filtro)
        
    if prioridad_filtro and prioridad_filtro != 'Todas':
        lista_incidencias = lista_incidencias.filter(prioridad=prioridad_filtro)

    # 4. Aplicamos Paginación: 10 incidencias por página
    paginator = Paginator(lista_incidencias, 10)
    page_number = request.GET.get('page')
    incidencias = paginator.get_page(page_number)

    # 5. Empaquetamos todo en el contexto para la plantilla
    return render(request, 'admin_gestion_incidencias.html', {
        'incidencias': incidencias,
        'query': query,
        'estado_filtro': estado_filtro,
        'prioridad_filtro': prioridad_filtro,
    })

@require_role([1, 4])
def admin_editar_incidencia(request, pk):
    ticket = get_object_or_404(TicketSoporte, pk=pk)

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado_ticket')
        nueva_observacion = request.POST.get('observacion', '').strip()
        
        if nuevo_estado:
            ticket.estado_ticket = nuevo_estado
            if nueva_observacion:
                ticket.observacion = nueva_observacion
            ticket.save(update_fields=['estado_ticket', 'observacion'])
            
            messages.success(request, f'¡Incidencia INC-2026-{ticket.id_ticket:03d} actualizada con éxito!')
            return redirect('admin_gestion_incidencias')

    context = {'ticket': ticket}
    return render(request, 'admin_editar_incidencia.html', context)

@require_role([1, 4])
def admin_detalle_incidencia(request, pk):
    ticket = get_object_or_404(TicketSoporte, pk=pk)
    return render(request, 'admin_detalle_incidencia.html', {'ticket': ticket})

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import SolicitudInsumo

def admin_solicitudes_material(request):
    # Seguridad básica de sesión de administrador
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    # Filtramos estrictamente las solicitudes de tipo 'Solicitud de Material'
    solicitudes = SolicitudInsumo.objects.filter(tipo_solicitud='Solicitud de Material').order_by('-fecha')
    
    context = {
        'solicitudes': solicitudes,
        'titulo': 'Solicitudes de Material (Aseo)'
    }
    return render(request, 'admin_gestion_solicitudes.html', context)

def admin_solicitudes_reposicion(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    # Filtramos estrictamente las solicitudes de tipo 'Solicitud de Reposición'
    solicitudes = SolicitudInsumo.objects.filter(tipo_solicitud='Solicitud de Reposición').order_by('-fecha')
    
    context = {
        'solicitudes': solicitudes,
        'titulo': 'Solicitudes de Reposición (Aseo)'
    }
    return render(request, 'admin_gestion_solicitudes.html', context)



from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .models import Usuario

# --- GESTIÓN DE PROFESORES ---

from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .models import Usuario, Curso, Asignatura, AsignaturaCurso

from django.core.paginator import Paginator
from django.db.models import Q

@require_role([1, 4])
def admin_gestion_profesores(request):
    query = request.GET.get('q', '').strip()
    asignatura_filtro = request.GET.get('asignatura', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()

    # 1. Traer todos los usuarios con rol 2 (Profesor)
    profesores_qs = Usuario.objects.filter(rol_id_rol_id=2).order_by('apellido_paterno', 'nombre')

    # 2. Búsqueda profesional por nombre, apellidos, RUT y correo (soporta múltiples palabras)
    if query:
        palabras = query.split()
        for palabra in palabras:
            profesores_qs = profesores_qs.filter(
                Q(nombre__icontains=palabra) |
                Q(apellido_paterno__icontains=palabra) |
                Q(apellido_materno__icontains=palabra) |
                Q(rut__icontains=palabra) |
                Q(correo__icontains=palabra)
            )

    if estado_filtro == 'Activos':
        profesores_qs = profesores_qs.filter(activo=1)
    elif estado_filtro == 'Inactivos':
        profesores_qs = profesores_qs.filter(activo=0)

    if asignatura_filtro and asignatura_filtro != 'Todas':
        ruts_con_asignatura = AsignaturaCurso.objects.filter(
            asignatura_id_asignatura_id=asignatura_filtro
        ).values_list('usuario_rut_id', flat=True)
        profesores_qs = profesores_qs.filter(rut__in=ruts_con_asignatura)

    # 3. Aplicar Paginación (10 profesores por página)
    paginator = Paginator(profesores_qs, 10)
    page_number = request.GET.get('page')
    pagina_profesores = paginator.get_page(page_number)

    # 4. Cruzar cada profesor de la página actual con sus jefaturas y asignaciones
    lista_profesores = []
    for p in pagina_profesores:
        partes_iniciales = f"{(p.nombre or '')[:1]}{(p.apellido_paterno or '')[:1]}".upper()
        p.iniciales = partes_iniciales if partes_iniciales else "PR"
        
        # Cursos donde es Profesor Jefe
        p.jefaturas = Curso.objects.filter(usuario_rut=p)
        
        # Ramos y cursos que imparte
        p.asignaciones = AsignaturaCurso.objects.filter(usuario_rut=p).select_related(
            'curso_id_curso', 'asignatura_id_asignatura'
        ).order_by('curso_id_curso__nombre_curso', 'asignatura_id_asignatura__nombre_asignatura')
        
        lista_profesores.append(p)

    pagina_profesores.object_list = lista_profesores

    asignaturas_disponibles = Asignatura.objects.all().order_by('nombre_asignatura')

    return render(request, 'admin_gestion_profesores.html', {
        'profesores': pagina_profesores,
        'asignaturas_disponibles': asignaturas_disponibles,
        'query': query,
        'asignatura_filtro': asignatura_filtro,
        'estado_filtro': estado_filtro,
    })


@require_role([1, 4])
def admin_editar_profesor(request):
    rut_seleccionado = request.GET.get('rut', '').strip() or request.POST.get('profesor_rut', '').strip()

    profesores = Usuario.objects.filter(rol_id_rol_id=2, activo=1).order_by('apellido_paterno', 'nombre')
    cursos = Curso.objects.all().order_by('id_curso')
    asignaturas = Asignatura.objects.all().order_by('nombre_asignatura')

    if request.method == 'POST':
        accion = request.POST.get('accion', 'asignar')

        if accion == 'eliminar':
            id_asig_curso = request.POST.get('id_asig_curso')
            asignacion = AsignaturaCurso.objects.filter(id_asig_curso=id_asig_curso).first()
            if asignacion:
                rut_prof = asignacion.usuario_rut_id
                asignacion.delete()
                messages.success(request, 'Asignación eliminada correctamente.')
                return redirect(f"/administrador/profesores/editar/?rut={rut_prof}")
            return redirect('admin_gestion_profesores')

        profesor_rut = request.POST.get('profesor_rut', '').strip()
        curso_id = request.POST.get('curso_id', '').strip()
        asignatura_id = request.POST.get('asignatura_id', '').strip()
        es_jefe = request.POST.get('es_profesor_jefe') == 'on'

        if not profesor_rut or not curso_id or not asignatura_id:
            messages.error(request, 'Debes seleccionar el profesor, el curso y la asignatura.')
            return redirect('admin_editar_profesor')

        profesor_obj = get_object_or_404(Usuario, rut=profesor_rut)
        curso_obj = get_object_or_404(Curso, id_curso=curso_id)
        asignatura_obj = get_object_or_404(Asignatura, id_asignatura=asignatura_id)

        # Si marcaron el check de Profesor Jefe, actualizamos la tabla curso usando el ID directo
        if es_jefe:
            Curso.objects.filter(id_curso=curso_obj.id_curso).update(usuario_rut=profesor_obj)

        # Verificar si ese curso ya tiene asignada esa asignatura
        existente = AsignaturaCurso.objects.filter(
            curso_id_curso=curso_obj,
            asignatura_id_asignatura=asignatura_obj
        ).first()

        if existente:
            existente.usuario_rut = profesor_obj
            existente.save()
            messages.success(
                request,
                f'Se actualizó {asignatura_obj.nombre_asignatura} en {curso_obj.nombre_curso} para {profesor_obj.nombre} {profesor_obj.apellido_paterno}.'
            )
        else:
            ultimo_id = AsignaturaCurso.objects.aggregate(max_id=Max('id_asig_curso'))['max_id'] or 0
            AsignaturaCurso.objects.create(
                id_asig_curso=ultimo_id + 1,
                curso_id_curso=curso_obj,
                asignatura_id_asignatura=asignatura_obj,
                usuario_rut=profesor_obj
            )
            messages.success(
                request,
                f'Asignación creada: {profesor_obj.nombre} {profesor_obj.apellido_paterno} → {asignatura_obj.nombre_asignatura} ({curso_obj.nombre_curso}).'
            )

        return redirect(f"/administrador/profesores/editar/?rut={profesor_obj.rut}")

    asignaciones_actuales = AsignaturaCurso.objects.select_related(
        'curso_id_curso', 'asignatura_id_asignatura', 'usuario_rut'
    ).order_by('curso_id_curso__id_curso', 'asignatura_id_asignatura__nombre_asignatura')

    if rut_seleccionado:
        asignaciones_actuales = asignaciones_actuales.filter(usuario_rut_id=rut_seleccionado)

    return render(request, 'admin_editar_profesor.html', {
        'profesores': profesores,
        'cursos': cursos,
        'asignaturas': asignaturas,
        'rut_seleccionado': rut_seleccionado,
        'asignaciones_actuales': asignaciones_actuales,
    })


# --- GESTIÓN DE APODERADOS (Rol 3) ---

from django.core.paginator import Paginator
from django.db.models import Q

@require_role([1, 4])
def admin_gestion_apoderados(request):
    query = request.GET.get('q', '').strip()
    
    # 1. Obtenemos todos los apoderados (probando con el campo de rol correcto)
    # Si en tu modelo de Usuario la relación se llama diferente, asegúrate de mantener tu filtro base (ej. rol_id_rol_id=3 o rol_id_rol=3)
    try:
        apoderados_qs = Usuario.objects.filter(rol_id_rol_id=3).order_by('apellido_paterno', 'nombre')
    except Exception:
        apoderados_qs = Usuario.objects.filter(rol_id_rol=3).order_by('apellido_paterno', 'nombre')

    # 2. Búsqueda multi-palabra inteligente y segura
    if query:
        palabras = query.split()
        for palabra in palabras:
            apoderados_qs = apoderados_qs.filter(
                Q(nombre__icontains=palabra) |
                Q(apellido_paterno__icontains=palabra) |
                Q(apellido_materno__icontains=palabra) |
                Q(rut__icontains=palabra) |
                Q(correo__icontains=palabra)
            )

    # 3. Paginación formal: 10 apoderados por página
    paginator = Paginator(apoderados_qs, 10)
    page_number = request.GET.get('page')
    apoderados_paginados = paginator.get_page(page_number)

    # 4. Cruzamos de forma dinámica los pupilos asociados a cada apoderado
    lista_procesada = []
    for apo in apoderados_paginados:
        # Buscamos los alumnos que tienen este RUT como apoderado
        pupilos = Alumno.objects.filter(usuario_rut=apo).select_related('curso_id_curso')
        
        texto_pupilos = []
        for alumno in pupilos:
            curso_nombre = alumno.curso_id_curso.nombre_curso if alumno.curso_id_curso else "Sin curso"
            texto_pupilos.append(f"{alumno.nombre_completo} ({curso_nombre})")
            
        apo.pupilos_str = " - ".join(texto_pupilos) if texto_pupilos else ""
        lista_procesada.append(apo)

    apoderados_paginados.object_list = lista_procesada

    return render(request, 'admin_gestion_apoderados.html', {
        'apoderados': apoderados_paginados,
        'query': query,
    })

@require_role([1, 4])
def admin_editar_apoderado(request, rut):
    # Buscamos al apoderado por su RUT exacto
    apoderado = get_object_or_404(Usuario, rut=rut)
    
    # Buscamos sus pupilos asociados para mostrarlos en la vista
    pupilos = Alumno.objects.filter(usuario_rut=apoderado).select_related('curso_id_curso')

    if request.method == 'POST':
        apoderado.nombre = request.POST.get('nombre', '').strip()
        apoderado.apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apoderado.apellido_materno = request.POST.get('apellido_materno', '').strip()
        apoderado.correo = request.POST.get('correo', '').strip()
        apoderado.telefono = request.POST.get('telefono', '').strip()
        apoderado.direccion = request.POST.get('direccion', '').strip()
        apoderado.activo = 1 if 'activo' in request.POST else 0

        apoderado.save()
        messages.success(request, f"Apoderado {apoderado.nombre} actualizado correctamente.")
        return redirect('admin_gestion_apoderados')

    return render(request, 'admin_editar_apoderado.html', {
        'apoderado': apoderado,
        'pupilos': pupilos
    })


from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import EquipoTi, Insumo, SolicitudInsumo

@require_role([1, 4])
def inventario_ti(request):
    query = request.GET.get('q', '').strip()
    
    # 1. Consulta base ordenada por código de inventario
    equipos_qs = EquipoTi.objects.all().order_by('codigo_inventario')

    # 2. Búsqueda inteligente multi-palabra (por código, ubicación, tipo o estado)
    if query:
        palabras = query.split()
        for palabra in palabras:
            equipos_qs = equipos_qs.filter(
                Q(codigo_inventario__icontains=palabra) |
                Q(ubicacion__icontains=palabra) |
                Q(tipo_equipo__icontains=palabra) |
                Q(estado__icontains=palabra)
            )

    # 3. Contadores totales basados en el total general de la BD
    todos_equipos = EquipoTi.objects.all()
    total_equipos = todos_equipos.count()
    operativos = todos_equipos.filter(estado__iexact='Disponible').count()
    en_mantencion = todos_equipos.filter(estado__iexact='En Mantención').count()

    # 4. Paginación: 10 equipos por página
    paginator = Paginator(equipos_qs, 10)
    page_number = request.GET.get('page')
    equipos_paginados = paginator.get_page(page_number)

    return render(request, 'inventario_ti.html', {
        'equipos': equipos_paginados,
        'query': query,
        'total_equipos': total_equipos,
        'operativos': operativos,
        'en_mantencion': en_mantencion,
    })

@require_role([1, 4])
def admin_editar_equipo(request, codigo):
    # Buscamos el equipo exacto por su código de inventario
    equipo = get_object_or_404(EquipoTi, codigo_inventario=codigo)

    if request.method == 'POST':
        equipo.codigo_inventario = request.POST.get('codigo_inventario', '').strip()
        equipo.tipo_equipo = request.POST.get('tipo_equipo', '').strip()
        equipo.ubicacion = request.POST.get('ubicacion', '').strip()
        equipo.estado = request.POST.get('estado', 'Disponible')
        # Si tienes campo de observaciones o descripción en tu modelo:
        # equipo.observaciones = request.POST.get('observaciones', '').strip()

        equipo.save()
        messages.success(request, f"Equipo {equipo.codigo_inventario} actualizado correctamente.")
        return redirect('inventario_ti')

    return render(request, 'admin_editar_equipo.html', {
        'equipo': equipo
    })

@require_role([1, 4])
def crear_equipo_ti(request):
    if request.method == 'POST':
        codigo_inventario = request.POST.get('codigo_inventario')
        tipo_equipo = request.POST.get('tipo_equipo')
        ubicacion = request.POST.get('ubicacion')
        estado = request.POST.get('estado', 'Disponible')

        EquipoTi.objects.create(
            codigo_inventario=codigo_inventario,
            tipo_equipo=tipo_equipo,
            ubicacion=ubicacion,
            estado=estado
        )
        messages.success(request, 'Equipo tecnológico registrado exitosamente.')
        return redirect('inventario_ti')

    return render(request, 'crear_equipo_ti.html')

@require_role([1, 5])  # Administrador y Personal de Aseo

def incidencias_personal_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    # Mostramos las solicitudes de aseo ordenadas de la más reciente a la más antigua
    solicitudes = SolicitudInsumo.objects.all().order_by('-id_solicitud')
    return render(request, 'incidencias_personal_aseo.html', {'solicitudes': solicitudes})


def inventario_personal_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    items = Insumo.objects.all()
    return render(request, 'inventario_personal_aseo.html', {'items': items})


def retirar_stock_aseo(request, id_insumo):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    insumo = get_object_or_404(Insumo, pk=id_insumo)
    
    if request.method == 'POST':
        try:
            cantidad = int(request.POST.get('cantidad', 0))
        except ValueError:
            cantidad = 0
            
        if cantidad <= 0:
            messages.error(request, 'Debes ingresar una cantidad mayor a 0.')
        elif cantidad > insumo.stock_actual:
            messages.error(request, f'No puedes retirar {cantidad} unidades. Solo hay {insumo.stock_actual} disponibles.')
        else:
            insumo.stock_actual -= cantidad
            insumo.save()
            messages.success(request, f'Retiraste {cantidad} unidades de "{insumo.nombre_item}".')
            return redirect('inventario_aseo')
            
    return render(request, 'retirar_stock_aseo.html', {'insumo': insumo})

from django.db.models import Max

@require_role([1, 5])
def crear_insumo_aseo(request):
    if request.method == 'POST':
        nombre_item = request.POST.get('nombre_item')
        stock_actual = request.POST.get('stock_actual', 0)
        
        # Calculamos el siguiente ID disponible para evitar el error de columna nula
        ultimo_id = Insumo.objects.aggregate(max_id=Max('id_insumo'))['max_id'] or 0
        nuevo_id = ultimo_id + 1

        # Guardamos el nuevo insumo incluyendo explícitamente el id_insumo
        Insumo.objects.create(
            id_insumo=nuevo_id,
            nombre_item=nombre_item,
            stock_actual=stock_actual
        )
        messages.success(request, 'Insumo de aseo registrado exitosamente.')
        return redirect('inventario_aseo')
        
    return render(request, 'crear_insumo_aseo.html')


from django.contrib.auth.hashers import make_password
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Usuario

def cambiar_password_obligatorio(request):  # Usa el nombre que tengas en tus rutas
    rut_usuario = request.session.get('usuario_rut')
    if not rut_usuario:
        return redirect('login')
        
    usuario = Usuario.objects.get(rut=rut_usuario)
    
    if request.method == 'POST':
        nueva_pass = request.POST.get('nueva_password')
        confirma_pass = request.POST.get('conf_password') # 📌 Coincide con tu HTML (conf_password)
        correo_recup = request.POST.get('correo_recuperacion')
        
        if not nueva_pass or nueva_pass != confirma_pass:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, 'cambiar_password.html', {'usuario': usuario})
            
        if not correo_recup:
            messages.error(request, "Debes ingresar tu correo de recuperación personal.")
            return render(request, 'cambiar_password.html', {'usuario': usuario})
            
        # 1. Guardamos la nueva contraseña cifrada
        usuario.password_hash = make_password(nueva_pass)
        
        # 2. Guardamos el Gmail personal de rescate
        usuario.correo_recuperacion = correo_recup.strip().lower()
        
        # 3. 📌 Apagamos el bloqueo para que el login lo deje pasar libremente en el futuro
        usuario.cambiar_password = False
        usuario.save()
        
        # Limpiamos la sesión temporal de cambio
        request.session['debe_cambiar_pass'] = False
        
        messages.success(request, "¡Contraseña actualizada con éxito!")
        
        # Redirigimos según su rol
        rol = usuario.rol_id_rol.id_rol
        if rol in [1, 4]:
            return redirect('admin_inicio')
        elif rol == 2:
            return redirect('profesor_inicio')
        elif rol == 3:
            return redirect('apoderado_inicio')
        elif rol == 5:
            return redirect('inicio_supervisor_aseo')
            
    return render(request, 'cambiar_password.html', {'usuario': usuario})


def cambiar_password_perfil(request):
    # Seguridad: verificar que haya iniciado sesión
    if 'usuario_rut' not in request.session:
        messages.error(request, 'Debes iniciar sesión para realizar esta acción.')
        return redirect('login')

    try:
        usuario = Usuario.objects.get(rut=request.session['usuario_rut'])
    except Usuario.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        pass_actual = request.POST.get('password_actual', '').strip()
        nueva_pass = request.POST.get('nueva_password', '').strip()
        conf_pass = request.POST.get('conf_password', '').strip()
        correo_recup = request.POST.get('correo_recuperacion', '').strip().lower() # 📌 Capturamos el correo personal

        # 1. Validar que la contraseña actual sea correcta
        if not check_password(pass_actual, usuario.password_hash):
            messages.error(request, 'La contraseña actual es incorrecta.')
            return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

        # 2. Validar longitud mínima
        if not nueva_pass or len(nueva_pass) < 6:
            messages.error(request, 'La nueva contraseña debe tener al menos 6 caracteres.')
            return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

        # 3. Validar reglas de seguridad (Mayúscula, número y símbolo)
        tiene_mayuscula = any(c.isupper() for c in nueva_pass)
        tiene_numero = any(c.isdigit() for c in nueva_pass)
        tiene_simbolo = any(not c.isalnum() for c in nueva_pass)

        if not (tiene_mayuscula and tiene_numero and tiene_simbolo):
            messages.error(request, 'La contraseña nueva debe contener al menos una letra mayúscula, un número y un símbolo especial.')
            return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

        # 4. Validar coincidencia
        if nueva_pass != conf_pass:
            messages.error(request, 'Las nuevas contraseñas ingresadas no coinciden.')
            return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

        # 5. Guardar la nueva contraseña cifrada y el correo de recuperación
        usuario.password_hash = make_password(nueva_pass)
        if correo_recup:
            usuario.correo_recuperacion = correo_recup
            
        # Guardamos ambos campos en la base de datos legacy
        usuario.save(update_fields=['password_hash', 'correo_recuperacion'])

        messages.success(request, '¡Tu contraseña y datos de seguridad han sido actualizados con éxito!')

        # Redirigir de vuelta a su panel correspondiente según su rol
        rol = usuario.rol_id_rol.id_rol
        if rol in [1, 4]:
            return redirect('admin_inicio')
        elif rol == 2:
            return redirect('profesor_inicio')
        elif rol == 3:
            return redirect('apoderado_inicio')
        elif rol == 5:
            return redirect('inicio_supervisor_aseo')

    # Cuando es método GET, enviamos el objeto usuario para que pinte su correo si ya lo tenía guardado
    return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

from datetime import date
from django.contrib import messages
from django.db import transaction
from django.db.models import Max
from django.shortcuts import redirect, render
from django.utils import timezone
from .models import Usuario, EquipoTi, SolicitudInsumo, TicketSoporte, Rol

@require_role([1, 4])  # Solo Administrador y TI
def admin_crear_incidencia(request):
    tipos = {
        'material': ('insumo', 'Solicitud de Material'),
        'reposicion': ('insumo', 'Solicitud de Reposición'),
        'equipo': ('soporte', 'Problema con Equipo'),
        'mantenimiento': ('soporte', 'Mantenimiento'),
    }

    equipos = list(EquipoTi.objects.all().order_by('codigo_inventario'))

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
        equipo.nombre_equipo = tipos_equipos.get(prefijo, 'Equipo tecnológico')

    if request.method == 'POST':
        fecha_texto = request.POST.get('fecha', '').strip()
        tipo = request.POST.get('tipo', '').strip()
        descripcion = request.POST.get('descripcion', '').strip()
        codigo_equipo = request.POST.get('equipo', '').strip()
        
        # 📌 1. AQUÍ CAPTURAMOS LA PRIORIDAD SELECCIONADA EN EL FORMULARIO
        prioridad = request.POST.get('prioridad', 'Media').strip()

        try:
            fecha = date.fromisoformat(fecha_texto)
        except ValueError:
            messages.error(request, 'La fecha ingresada no es válida.')
            return redirect('admin_crear_incidencia')

        if tipo not in tipos:
            messages.error(request, 'Selecciona un tipo de incidencia válido.')
            return redirect('admin_crear_incidencia')

        if not descripcion:
            messages.error(request, 'Debes ingresar una descripción.')
            return redirect('admin_crear_incidencia')

        rut_admin = request.session.get('usuario_rut')

        if not rut_admin or not Usuario.objects.filter(rut=rut_admin).exists():
            messages.error(request, 'No se encontró el usuario de la sesión.')
            return redirect('admin_crear_incidencia')

        destino, nombre_tipo = tipos[tipo]
        equipo = None

        if destino == 'soporte':
            if not codigo_equipo:
                messages.error(request, 'Debes seleccionar el equipo involucrado.')
                return redirect('admin_crear_incidencia')

            equipo = EquipoTi.objects.filter(codigo_inventario=codigo_equipo).first()

            if equipo is None:
                messages.error(request, 'El equipo seleccionado no existe.')
                return redirect('admin_crear_incidencia')

        try:
            with transaction.atomic():
                if destino == 'insumo':
                    ultimo_id = SolicitudInsumo.objects.aggregate(max_id=Max('id_solicitud'))['max_id'] or 0
                    SolicitudInsumo.objects.create(
                        id_solicitud=ultimo_id + 1,
                        fecha=fecha,
                        estado_solicitud='Pendiente',
                        usuario_rut_id=rut_admin,
                        descripcion=descripcion,
                        tipo_solicitud=nombre_tipo
                    )
                else:
                    ultimo_id = TicketSoporte.objects.aggregate(max_id=Max('id_ticket'))['max_id'] or 0
                    TicketSoporte.objects.create(
                        id_ticket=ultimo_id + 1,
                        fecha_reporte=fecha,
                        prioridad=prioridad,  # 📌 2. AQUÍ GUARDAMOS LA PRIORIDAD REAL EN VEZ DE 'Media' FIJA
                        usuario_rut_id=rut_admin,
                        equipo_ti_codigo_inventario=equipo,
                        descripcion=descripcion,
                        tipo_incidencia=nombre_tipo
                    )
        except Exception:
            messages.error(request, 'No se pudo guardar la incidencia. Revisa la base de datos.')
            return redirect('admin_crear_incidencia')

        messages.success(request, f'{nombre_tipo} registrada correctamente.')
        return redirect('admin_gestion_incidencias')

    return render(request, 'admin_agregar_incidencia.html', {
        'equipos': equipos,
        'fecha_actual': timezone.localdate().isoformat()
    })

from django.core.paginator import Paginator

@require_role([1, 5])
def inicio_supervisor_aseo(request):
    total_articulos = Insumo.objects.count()
    stock_critico = Insumo.objects.filter(stock_actual__lte=5).count()
    
    # 1. Obtenemos la lista de RUTs de usuarios con Rol 5 (Aseo)
    ruts_aseo = Usuario.objects.filter(rol_id_rol=5).values_list('rut', flat=True)
    
    # 2. Contamos las solicitudes PENDIENTES hechas por esos usuarios
    solicitudes_pendientes = SolicitudInsumo.objects.filter(
        usuario_rut__in=ruts_aseo,
        estado_solicitud='Pendiente'
    ).count()

    context = {
        'total_articulos': total_articulos,
        'stock_critico': stock_critico,
        'solicitudes_pendientes': solicitudes_pendientes,
    }
    return render(request, 'inicio_supervisor_aseo.html', context)


@require_role([1, 5])
def incidencias_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    # 1. Obtenemos la lista de RUTs de usuarios con Rol 5 (Aseo)
    ruts_aseo = Usuario.objects.filter(rol_id_rol=5).values_list('rut', flat=True)

    # 2. Traemos únicamente las solicitudes asociadas a esos RUTs
    lista_solicitudes = SolicitudInsumo.objects.filter(
        usuario_rut__in=ruts_aseo
    ).order_by('-id_solicitud')
    
    paginator = Paginator(lista_solicitudes, 10)
    page_number = request.GET.get('page')
    solicitudes = paginator.get_page(page_number)
    
    context = {
        'solicitudes': solicitudes,
        'rol_id': request.session.get('rol_id')
    }
    return render(request, 'incidencias_aseo.html', context)


def inventario_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    lista_items = Insumo.objects.all().order_by('id_insumo')
    
    # Paginación: 10 insumos por página
    paginator = Paginator(lista_items, 10)
    page_number = request.GET.get('page')
    items = paginator.get_page(page_number)
    
    context = {
        'items': items,
        'rol_id': request.session.get('rol_id')
    }
    return render(request, 'inventario_aseo.html', context)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Max
from datetime import date
from .models import SolicitudInsumo, Usuario

@require_role([1, 5])
def crear_incidencia_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')

    if request.method == 'POST':
        tipo_solicitud = request.POST.get('tipo_incidencia')
        descripcion = request.POST.get('descripcion')
        fecha_incidencia = request.POST.get('fecha_incidencia') or date.today()
        rut_sesion = request.session.get('usuario_rut')

        try:
            usuario_obj = get_object_or_404(Usuario, pk=rut_sesion)

            max_id = SolicitudInsumo.objects.aggregate(Max('id_solicitud'))['id_solicitud__max']
            nuevo_id = (max_id or 0) + 1

            SolicitudInsumo.objects.create(
                id_solicitud=nuevo_id,
                fecha=fecha_incidencia,
                tipo_solicitud=tipo_solicitud,
                descripcion=descripcion,
                estado_solicitud='Pendiente',
                usuario_rut=usuario_obj
            )

            messages.success(request, '¡Solicitud de aseo registrada con éxito!')
            return redirect('incidencias_aseo')

        except Exception as e:
            messages.error(request, f'Ocurrió un error al guardar la solicitud: {str(e)}')
            return render(request, 'crear_incidencia_aseo.html')

    return render(request, 'crear_incidencia_aseo.html')


@require_role([1, 5])
def resolver_solicitud_aseo(request, id_solicitud):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    solicitud = get_object_or_404(SolicitudInsumo, id_solicitud=id_solicitud)
    
    if request.method == 'POST':
        try:
            nuevo_estado = request.POST.get('estado_solicitud', 'Resuelto')
            observaciones = request.POST.get('observaciones', '')
            
            solicitud.estado_solicitud = nuevo_estado
            solicitud.observaciones = observaciones
            solicitud.save()
            
            messages.success(request, f'¡Solicitud #{id_solicitud} actualizada correctamente!')
            return redirect('incidencias_aseo')

        except Exception as e:
            messages.error(request, f'Error al actualizar la solicitud: {str(e)}')
        
    context = {
        'solicitud': solicitud
    }
    return render(request, 'resolver_solicitud_aseo.html', context)


@require_role([1, 5])
def ajustar_stock_insumo(request, id_insumo):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    insumo = get_object_or_404(Insumo, pk=id_insumo)
    
    if request.method == 'POST':
        accion = request.POST.get('accion') # 'sumar', 'restar', 'fijar'
        
        try:
            cantidad = int(request.POST.get('cantidad', 0))
            if cantidad < 0:
                messages.warning(request, 'La cantidad debe ser un número positivo.')
                return render(request, 'ajustar_stock_insumo.html', {'insumo': insumo})
                
            if accion == 'sumar':
                insumo.stock_actual += cantidad
            elif accion == 'restar':
                insumo.stock_actual = max(0, insumo.stock_actual - cantidad)
            elif accion == 'fijar':
                insumo.stock_actual = max(0, cantidad)
                
            insumo.save()
            messages.success(request, f'¡Stock de "{insumo.nombre_item}" actualizado con éxito!')
            return redirect('inventario_aseo')

        except ValueError:
            messages.error(request, 'Por favor ingrese una cantidad numérica válida.')
        except Exception as e:
            messages.error(request, f'Error al guardar en base de datos: {str(e)}')
        
    context = {
        'insumo': insumo
    }
    return render(request, 'ajustar_stock_insumo.html', context)

import random
import string
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from .models import Usuario

def recuperar_contrasena(request):
    if request.method == 'POST':
        correo_ingresado = request.POST.get('correo', '').strip().lower()
        
        try:
            usuario = Usuario.objects.get(correo=correo_ingresado)
            
            # Validar que tenga un Gmail personal registrado
            if not usuario.correo_recuperacion:
                messages.error(request, "Esta cuenta no tiene asociado un correo de recuperación personal. Contacte a soporte.")
                return render(request, 'recuperar_contrasena.html')
            
            # Generar clave temporal
            caracteres = string.ascii_letters + string.digits
            temp_password = "".join(random.choice(caracteres) for _ in range(8))
            
            # Guardar hash y activar el flag de cambio obligatorio
            usuario.password_hash = make_password(temp_password)
            usuario.cambiar_password = True
            usuario.save()
            
            # Enviar correo real por SMTP a su Gmail personal
            asunto = "Recuperación de Contraseña - SGE Santa Juliana"
            mensaje = (
                f"Hola {usuario.nombre or 'Usuario'},\n\n"
                f"Has solicitado restablecer tu contraseña.\n"
                f"Tu contraseña temporal de acceso es: {temp_password}\n\n"
                f"Al ingresar al sistema deberás cambiarla obligatoriamente.\n\n"
                f"Atentamente,\nSoporte TI - Colegio Santa Juliana"
            )
            
            send_mail(
                asunto,
                mensaje,
                None,
                [usuario.correo_recuperacion], # 📌 Envía al Gmail personal
                fail_silently=False,
            )
            
            messages.success(request, "¡Instrucciones enviadas con éxito a tu correo de recuperación!")
            return redirect('login')
            
        except Usuario.DoesNotExist:
            messages.error(request, "No se encontró ninguna cuenta asociada a este correo institucional.")
            
    return render(request, 'recuperar_contrasena.html')

