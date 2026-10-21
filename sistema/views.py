from datetime import datetime

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
                    return redirect('admin_gestion_inventario')


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
    return render(request, 'apoderado_inicio.html')

@require_role([3])
def apoderado_notas(request):
    return render(request, 'apoderado_notas.html')

@require_role([3])
def apoderado_asistencia(request):
    return render(request, 'apoderado_asistencia.html')

@require_role([3])
def apoderado_calendario(request):
    return render(request, 'apoderado_calendario.html')

@require_role([3])
def apoderado_certificados(request):
    return render(request, 'apoderado_certificados.html')

# Vistas para el portal de Profesores
@require_role([2])
def profesor_inicio(request):
    return render(request, 'profesor_inicio.html')


import json
from decimal import Decimal, InvalidOperation
from django.db import transaction, connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from sistema.models import Curso, Alumno, AsignaturaCurso, Evaluacion, Calificacion

@require_role([2])
@require_http_methods(['GET', 'POST'])
def profesor_notas(request):
    if request.method == 'POST':
        try:
            payload = json.loads(request.body)
            curso_id = int(payload['curso_id'])
            relacion_id = int(payload['asignatura_id'])
            columnas = payload['columnas']
            notas = payload['notas']
            if not isinstance(columnas, list) or not columnas or len(columnas) > 40 or not isinstance(notas, dict):
                raise ValueError('Datos inválidos.')
            if columnas != list(range(1, len(columnas) + 1)):
                raise ValueError('Las evaluaciones deben ser consecutivas.')
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return JsonResponse({'ok': False, 'error': 'Datos de solicitud inválidos.'}, status=400)

        relacion = AsignaturaCurso.objects.filter(id_asig_curso=relacion_id, curso_id_curso_id=curso_id).first()
        if not relacion:
            return JsonResponse({'ok': False, 'error': 'Curso o asignatura inválidos.'}, status=400)
        ruts_validos = set(Alumno.objects.filter(curso_id_curso_id=curso_id).values_list('rut_alumno', flat=True))
        if set(notas) != ruts_validos:
            return JsonResponse({'ok': False, 'error': 'La lista de alumnos no corresponde al curso.'}, status=400)
        parsed = {}
        for rut, valores in notas.items():
            if not isinstance(valores, list) or len(valores) != len(columnas):
                return JsonResponse({'ok': False, 'error': 'Cantidad de notas inválida.'}, status=400)
            for numero, valor in enumerate(valores, 1):
                if valor in ('', None):
                    continue
                try:
                    numero_nota = Decimal(str(valor).replace(',', '.'))
                except InvalidOperation:
                    return JsonResponse({'ok': False, 'error': f'Nota inválida de {rut}.'}, status=400)
                if not numero_nota.is_finite() or not (Decimal('1.0') <= numero_nota <= Decimal('7.0')) or numero_nota.as_tuple().exponent < -1:
                    return JsonResponse({'ok': False, 'error': f'Las notas deben estar entre 1.0 y 7.0, con un decimal ({rut}).'}, status=400)
                parsed[(rut, numero)] = float(numero_nota)

        try:
            with transaction.atomic():
                # Serializa los guardados de esta asignatura para evitar IDs repetidos.
                with connection.cursor() as cursor:
                    cursor.execute('SELECT id_asig_curso FROM asignatura_curso WHERE id_asig_curso = %s FOR UPDATE', [relacion_id])
                    cursor.execute('SELECT COALESCE(MAX(id_calificacion), 0) FROM calificacion')
                    max_id = cursor.fetchone()[0]
                existentes = {e.numero_evaluacion: e for e in Evaluacion.objects.filter(asignatura_curso_id_asig_curso_id=relacion_id)}
                # Mantener IDs de evaluaciones existentes; crear solo las faltantes.
                for numero in columnas:
                    if numero not in existentes:
                        existentes[numero] = Evaluacion.objects.create(asignatura_curso_id_asig_curso_id=relacion_id, numero_evaluacion=numero)
                for numero, evaluacion in list(existentes.items()):
                    if numero not in columnas:
                        Calificacion.objects.filter(evaluacion_id_evaluacion_id=evaluacion.id_evaluacion).delete()
                        evaluacion.delete()
                        del existentes[numero]
                actuales = {}
                for c in Calificacion.objects.filter(asignatura_curso_id_asig_curso_id=relacion_id, alumno_rut_alumno_id__in=ruts_validos, evaluacion_id_evaluacion__isnull=False).order_by('id_calificacion'):
                    clave = (c.alumno_rut_alumno_id, c.evaluacion_id_evaluacion.numero_evaluacion)
                    if clave in actuales:
                        raise ValueError('Hay notas duplicadas en la base de datos. Revisar antes de guardar.')
                    actuales[clave] = c
                for clave, nota in parsed.items():
                    if clave in actuales:
                        c = actuales.pop(clave)
                        if c.valor_nota != nota:
                            c.valor_nota = nota
                            c.fecha_ingreso = timezone.localdate()
                            c.save(update_fields=['valor_nota', 'fecha_ingreso'])
                    else:
                        max_id += 1
                        Calificacion.objects.create(id_calificacion=max_id, valor_nota=nota, fecha_ingreso=timezone.localdate(), alumno_rut_alumno_id=clave[0], asignatura_curso_id_asig_curso_id=relacion_id, evaluacion_id_evaluacion_id=existentes[clave[1]].id_evaluacion)
                for c in actuales.values():
                    c.delete()
        except Exception as exc:
            return JsonResponse({'ok': False, 'error': f'No se pudieron guardar las notas: {exc}'}, status=500)
        return JsonResponse({'ok': True, 'mensaje': 'Calificaciones guardadas correctamente.'})

    cursos = Curso.objects.all().order_by('id_curso')
    curso_id = request.GET.get('curso', '')
    asignatura_curso_id = request.GET.get('asignatura', '')
    curso_seleccionado = cursos.filter(id_curso=int(curso_id)).first() if curso_id.isdigit() else None
    relaciones = AsignaturaCurso.objects.select_related('asignatura_id_asignatura').order_by('asignatura_id_asignatura__nombre_asignatura')
    asignaturas_por_curso = {}
    for relacion in relaciones:
        asignaturas_por_curso.setdefault(str(relacion.curso_id_curso_id), []).append({'id': str(relacion.id_asig_curso), 'nombre': relacion.asignatura_id_asignatura.nombre_asignatura})
    asignatura_seleccionada = None
    alumnos = []
    columnas = [1, 2, 3]
    notas_guardadas = {}
    if curso_seleccionado and asignatura_curso_id.isdigit():
        asignatura_seleccionada = relaciones.filter(curso_id_curso=curso_seleccionado, id_asig_curso=int(asignatura_curso_id)).first()
        if asignatura_seleccionada:
            alumnos = list(Alumno.objects.filter(curso_id_curso=curso_seleccionado).order_by('nombre_completo', 'rut_alumno'))
            evaluaciones = list(Evaluacion.objects.filter(asignatura_curso_id_asig_curso=asignatura_seleccionada).order_by('numero_evaluacion'))
            if evaluaciones:
                columnas = list(range(1, max(3, max(e.numero_evaluacion for e in evaluaciones)) + 1))
            numeros = {e.id_evaluacion: e.numero_evaluacion for e in evaluaciones}
            for calificacion in Calificacion.objects.filter(asignatura_curso_id_asig_curso=asignatura_seleccionada, evaluacion_id_evaluacion_id__in=numeros):
                notas_guardadas.setdefault(calificacion.alumno_rut_alumno_id, {})[str(numeros[calificacion.evaluacion_id_evaluacion_id])] = f'{calificacion.valor_nota:.1f}'
    return render(request, 'profesor_notas.html', {'cursos': cursos, 'asignaturas_por_curso': asignaturas_por_curso, 'curso_seleccionado': curso_seleccionado, 'asignatura_seleccionada': asignatura_seleccionada, 'alumnos': alumnos, 'columnas': columnas, 'notas_guardadas': notas_guardadas})





@require_role([2])
def profesor_asistencia(request):
    import json
    from datetime import date
    from django.db import transaction
    from django.db.models import Max
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import RegistroAsistencia

    hoy = timezone.localdate()

    # ========================================
    # GUARDAR ASISTENCIA
    # ========================================
    if request.method == 'POST':
        try:
            datos = json.loads(request.body)

            fecha = date.fromisoformat(datos['fecha'])
            curso_id = int(datos['curso_id'])
            asignatura_id = int(datos['asignatura_id'])
            estados = datos['estados']

            if fecha != timezone.localdate():
                return JsonResponse({
                    'ok': False,
                    'error': 'Solo puedes registrar o modificar la asistencia del día actual.'
                }, status=400)

            if not isinstance(estados, dict):
                raise ValueError('Formato de asistencia inválido.')

            asignatura = AsignaturaCurso.objects.filter(
                id_asig_curso=asignatura_id,
                curso_id_curso_id=curso_id
            ).first()

            if asignatura is None:
                return JsonResponse({
                    'ok': False,
                    'error': 'La asignatura no pertenece al curso seleccionado.'
                }, status=400)

            ruts = set(
                Alumno.objects.filter(
                    curso_id_curso_id=curso_id
                ).values_list('rut_alumno', flat=True)
            )

            if not ruts or set(estados.keys()) != ruts:
                return JsonResponse({
                    'ok': False,
                    'error': 'Debes registrar la asistencia de todos los alumnos del curso.'
                }, status=400)

            if any(
                type(estado) is not int or estado not in (0, 1)
                for estado in estados.values()
            ):
                return JsonResponse({
                    'ok': False,
                    'error': 'Todos los alumnos deben estar marcados como presentes o ausentes.'
                }, status=400)

            with transaction.atomic():

                # Bloquear el curso durante el guardado.
                Curso.objects.select_for_update().get(
                    id_curso=curso_id
                )

                # Buscar asistencias de HOY en TODAS
                # las asignaturas del mismo curso.
                registros = list(
                    RegistroAsistencia.objects.select_for_update().filter(
                        fecha=fecha,
                        alumno_rut_alumno_id__in=ruts,
                        asignatura_curso_id_asig_curso__curso_id_curso_id=curso_id
                    )
                )

                registros_por_alumno = {}

                for registro in registros:
                    rut = registro.alumno_rut_alumno_id

                    registros_por_alumno.setdefault(
                        rut, []
                    ).append(registro)

                siguiente_id = (
                    RegistroAsistencia.objects.aggregate(
                        max_id=Max('id_asistencia')
                    )['max_id'] or 0
                )

                # Una sola asistencia diaria por alumno
                # en el flujo nuevo.
                for rut, estado in estados.items():

                    existentes = registros_por_alumno.get(
                        rut, []
                    )

                    if existentes:
                        # Sincronizar los registros antiguos
                        # que puedan existir en otras asignaturas.
                        for registro in existentes:
                            if registro.presente != estado:
                                registro.presente = estado
                                registro.save(
                                    update_fields=['presente']
                                )

                    else:
                        siguiente_id += 1

                        RegistroAsistencia.objects.create(
                            id_asistencia=siguiente_id,
                            fecha=fecha,
                            presente=estado,
                            alumno_rut_alumno_id=rut,
                            asignatura_curso_id_asig_curso=asignatura
                        )

            return JsonResponse({
                'ok': True,
                'mensaje': 'Asistencia del curso guardada correctamente. Se reflejará en todas las asignaturas.'
            })

        except (
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError
        ) as error:
            return JsonResponse({
                'ok': False,
                'error': str(error)
            }, status=400)

        except Exception:
            return JsonResponse({
                'ok': False,
                'error': 'No fue posible guardar la asistencia. Revisa la conexión o los registros existentes.'
            }, status=500)

    # ========================================
    # CONSULTAR ASISTENCIA
    # ========================================
    cursos = Curso.objects.all().order_by('id_curso')

    curso_id = request.GET.get('curso', '').strip()
    asignatura_id = request.GET.get(
        'asignatura', ''
    ).strip()

    fecha_texto = request.GET.get('fecha', '').strip()

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
            'La fecha ingresada no es válida.'
        )

    curso_seleccionado = None
    asignatura_seleccionada = None

    asignaturas = AsignaturaCurso.objects.none()
    alumnos = []

    presentes = 0
    ausentes = 0
    asistencia_guardada = False
    asistencia_completa = False
    registros_inconsistentes = False

    if curso_id.isdigit():

        curso_seleccionado = cursos.filter(
            id_curso=int(curso_id)
        ).first()

        if curso_seleccionado:

            asignaturas = (
                AsignaturaCurso.objects.filter(
                    curso_id_curso=curso_seleccionado
                )
                .select_related(
                    'asignatura_id_asignatura'
                )
                .order_by(
                    'asignatura_id_asignatura__nombre_asignatura'
                )
            )

            if asignatura_id.isdigit():
                asignatura_seleccionada = asignaturas.filter(
                    id_asig_curso=int(asignatura_id)
                ).first()

            if asignatura_seleccionada:

                alumnos = list(
                    Alumno.objects.filter(
                        curso_id_curso=curso_seleccionado
                    ).order_by(
                        'nombre_completo',
                        'rut_alumno'
                    )
                )

                ruts = [
                    alumno.rut_alumno
                    for alumno in alumnos
                ]

                # Leer TODAS las asignaturas del curso.
                registros = (
                    RegistroAsistencia.objects.filter(
                        fecha=fecha,
                        alumno_rut_alumno_id__in=ruts,
                        asignatura_curso_id_asig_curso__curso_id_curso=curso_seleccionado
                    )
                    .order_by('-id_asistencia')
                )

                estados_guardados = {}
                estados_encontrados = {}

                for registro in registros:
                    rut = registro.alumno_rut_alumno_id

                    estados_encontrados.setdefault(
                        rut, set()
                    ).add(registro.presente)

                    # Si existen registros anteriores
                    # en varias asignaturas, mostrar
                    # provisionalmente el de mayor ID.
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
                    len(estados_guardados) == len(alumnos)
                    and len(alumnos) > 0
                    and not registros_inconsistentes
                )

    return render(
        request,
        'profesor_asistencia.html',
        {
            'cursos': cursos,
            'curso_seleccionado': curso_seleccionado,
            'asignaturas': asignaturas,
            'asignatura_seleccionada': asignatura_seleccionada,
            'fecha_seleccionada': fecha.isoformat(),
            'fecha_actual': hoy.isoformat(),
            'alumnos': alumnos,
            'total_alumnos': len(alumnos),
            'presentes': presentes,
            'ausentes': ausentes,
            'asistencia_guardada': asistencia_guardada,
            'asistencia_completa': asistencia_completa,
            'registros_inconsistentes': registros_inconsistentes,
        }
    )



@require_role([2])
def profesor_agregar_incidencia(request):
    return render(request, 'profesor_agregar_incidencia.html')

@require_role([2])
def profesor_revisar_incidencias(request):
    return render(request, 'profesor_revisar_incidencias.html')




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

@require_role([1, 4])
def admin_gestion_usuarios(request):
    # 1. Extraemos todos los usuarios y traemos los datos de su rol asociado
    lista_usuarios = Usuario.objects.select_related('rol_id_rol').all()
    
    # 2. Capturamos lo que venga del buscador ('q') y del select ('rol')
    query = request.GET.get('q', '').strip()
    rol_filtro = request.GET.get('rol', '').strip()

    # 3. Si escribieron algo en el buscador, filtramos por nombre, apellidos, correo o RUT
    if query:
        lista_usuarios = lista_usuarios.filter(
            Q(nombre__icontains=query) |
            Q(apellido_paterno__icontains=query) |
            Q(apellido_materno__icontains=query) |
            Q(correo__icontains=query) |
            Q(rut__icontains=query)
        )

    # 4. Si seleccionaron un rol en el desplegable, filtramos por ese ID de rol
    if rol_filtro:
        lista_usuarios = lista_usuarios.filter(rol_id_rol_id=rol_filtro)

    # 5. Traemos todos los roles de la BD para llenar el <select> del HTML
    roles = Rol.objects.all()

    # Empaquetamos todo en el contexto
    context = {
        'usuarios': lista_usuarios,
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

            usuario.save()

            messages.success(request, f'Usuario {usuario.rut} actualizado correctamente.')
            return redirect('admin_gestion_usuarios')

        except IntegrityError:
            messages.error(request, 'Error de integridad al intentar actualizar los datos.')
            return render(request, 'admin_editar_usuario.html', {'usuario': usuario, 'roles': roles})

    return render(request, 'admin_editar_usuario.html', {'usuario': usuario, 'roles': roles})
@require_role([1, 4])
def admin_eliminar_usuario(request, rut):
    # Buscamos al usuario o tiramos error 404 si no existe
    usuario = get_object_or_404(Usuario, rut=rut)
    
    # Lo eliminamos de la base de datos
    usuario.delete()
    
    # Opcional: un mensaje de éxito
    messages.success(request, 'Usuario eliminado correctamente.')
    
    # Redirigimos de vuelta a la tabla principal
    return redirect('admin_gestion_usuarios')

@require_role([1])
def admin_alumnos(request):
    alumnos = Alumno.objects.select_related(
        'curso_id_curso'
    ).order_by('nombre_completo')

    cursos = Curso.objects.all().order_by('id_curso')

    curso_seleccionado = request.GET.get('curso', '')

    if curso_seleccionado:
        alumnos = alumnos.filter(
            curso_id_curso_id=curso_seleccionado
        )

    context = {
        'alumnos': alumnos,
        'cursos': cursos,
        'curso_seleccionado': curso_seleccionado,
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


@require_role([1, 4])
def admin_gestion_incidencias(request):
    return render(request, 'admin_gestion_incidencias.html')

@require_role([1, 4])
def admin_editar_incidencia(request):
    return render(request, 'admin_editar_incidencia.html')

@require_role([1])
def admin_gestion_apoderados(request):
    return render(request, 'admin_gestion_apoderados.html')

@require_role([1])
def admin_editar_apoderado(request):
    return render(request, 'admin_editar_apoderado.html')

@require_role([1])
def admin_gestion_profesores(request):
    return render(request, 'admin_gestion_profesores.html')

@require_role([1])
def admin_editar_profesor(request):
    return render(request, 'admin_editar_profesor.html')

@require_role([1, 4, 5])
def admin_gestion_inventario(request):
    return render(request, 'admin_gestion_inventario.html')

@require_role([1, 4])
def admin_editar_equipo(request):
    return render(request, 'admin_editar_equipo.html')

def cambiar_password_obligatorio(request):
    # Seguridad: si no pasó por el login o no tiene la bandera activa, lo devolvemos
    if 'usuario_rut' not in request.session or not request.session.get('debe_cambiar_pass'):
        return redirect('login')

    if request.method == 'POST':
        nueva_pass = request.POST.get('nueva_password', '').strip()
        conf_pass = request.POST.get('conf_password', '').strip()

        # 1. Validar longitud mínima (ej: 6 u 8 caracteres)
        if not nueva_pass or len(nueva_pass) < 6:
            messages.error(request, 'La nueva contraseña debe tener al menos 6 caracteres.')
            return render(request, 'cambiar_password.html')

        # 2. Validar reglas de seguridad (Mayúscula, número y símbolo)
        tiene_mayuscula = any(c.isupper() for c in nueva_pass)
        tiene_numero = any(c.isdigit() for c in nueva_pass)
        tiene_simbolo = any(not c.isalnum() for c in nueva_pass)

        if not (tiene_mayuscula and tiene_numero and tiene_simbolo):
            messages.error(request, 'La contraseña debe contener al menos una letra mayúscula, un número y un símbolo especial.')
            return render(request, 'cambiar_password.html')

        # 3. Validar coincidencia
        if nueva_pass != conf_pass:
            messages.error(request, 'Las contraseñas ingresadas no coinciden.')
            return render(request, 'cambiar_password.html')

        try:
            # Buscamos al usuario y actualizamos su clave encriptada
            usuario = Usuario.objects.get(rut=request.session['usuario_rut'])
            usuario.password_hash = make_password(nueva_pass)
            usuario.cambiar_password = False  # Apagamos la bandera
            usuario.save(update_fields=['password_hash', 'cambiar_password'])

            # ¡MANTENEMOS LA SESIÓN ACTIVA Y CONFIGURAMOS SU HORA DE ACCESO!
            request.session['ultimo_acceso'] = datetime.now().strftime('%d/%m/%Y a las %H:%M')
            request.session['usuario_rut'] = usuario.rut
            request.session['rol_id'] = usuario.rol_id_rol.id_rol
            request.session['nombre_usuario'] = usuario.nombre
            request.session['apellido_usuario'] = usuario.apellido_paterno
            request.session['rol_nombre'] = usuario.rol_id_rol.nombre_rol

            # Borramos la bandera temporal de cambio obligatorio
            if 'debe_cambiar_pass' in request.session:
                del request.session['debe_cambiar_pass']

            messages.success(request, '¡Contraseña actualizada con éxito!')

            # REDIRIGIMOS DIRECTO A SU PANEL CORRESPONDIENTE (Adiós al login)
            rol = usuario.rol_id_rol.id_rol
            if rol in [1, 4]:
                return redirect('admin_inicio')
            elif rol == 2:
                return redirect('profesor_inicio')
            elif rol == 3:
                return redirect('apoderado_inicio')
            elif rol == 5:
                return redirect('admin_gestion_inventario')

        except Usuario.DoesNotExist:
            messages.error(request, 'Ocurrió un error al actualizar la cuenta.')
            return redirect('login')
        
    return render(request, 'cambiar_password.html')