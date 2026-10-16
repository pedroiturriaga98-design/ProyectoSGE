from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from functools import wraps # Importante para hacer decoradores
from .models import Usuario, Curso, Alumno, AsignaturaCurso
from django.db import IntegrityError, transaction

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
        # Le cambié el nombre a la variable para que tenga más sentido
        credencial_ingresada = request.POST.get('username') 
        password_ingresada = request.POST.get('password')

        try:
            # 1. Buscamos al usuario de forma inteligente (por correo o por RUT)
            if '@' in credencial_ingresada:
                usuario = Usuario.objects.get(correo=credencial_ingresada)
            else:
                usuario = Usuario.objects.get(rut=credencial_ingresada)

            # 2. Comparamos la contraseña 
            if usuario.password_hash == password_ingresada:
                
                # 3. Guardamos su sesión (el "ticket" del navegador)
                request.session['usuario_rut'] = usuario.rut
                request.session['rol_id'] = usuario.rol_id_rol.id_rol
                
                # ¡AQUÍ ESTÁ LA MAGIA PARA EL HEADER! Guardamos estos datos extra:
                request.session['nombre_usuario'] = usuario.nombre
                request.session['apellido_usuario'] = usuario.apellido_paterno
                # Asumo que la columna en tu modelo Rol se llama nombre_rol. Si se llama distinto, ajústalo.
                request.session['rol_nombre'] = usuario.rol_id_rol.nombre_rol 

                # 4. Redirigimos según el Rol usando los nombres de tus vistas
                rol = usuario.rol_id_rol.id_rol
                if rol == 1: # Administrador
                    return redirect('admin_inicio')
                elif rol == 2: # Profesor
                    return redirect('profesor_inicio')
                elif rol == 3: # Apoderado
                    return redirect('apoderado_inicio')
                else:
                    messages.error(request, 'El usuario no tiene un rol válido asignado.')
            else:
                messages.error(request, 'Contraseña incorrecta.')
                
        except Usuario.DoesNotExist:
            messages.error(request, 'El usuario o correo ingresado no existe en el sistema.')

    # Si entra por primera vez (GET), muestra la página normal
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

@require_role([2])
def profesor_notas(request):
    return render(request, 'profesor_notas.html')

@require_role([2])
def profesor_asistencia(request):
    return render(request, 'profesor_asistencia.html')

@require_role([2])
def profesor_agregar_incidencia(request):
    return render(request, 'profesor_agregar_incidencia.html')

@require_role([2])
def profesor_revisar_incidencias(request):
    return render(request, 'profesor_revisar_incidencias.html')


@require_role([2])
def profesor_alumnos(request):

    # Profesor que inició sesión
    profesor_rut = request.session.get('usuario_rut')

    # Cursos asignados directamente al profesor
    cursos_directos = Curso.objects.filter(
        usuario_rut_id=profesor_rut
    ).values_list('id_curso', flat=True)

    # Cursos donde el profesor imparte alguna asignatura
    cursos_asignaturas = AsignaturaCurso.objects.filter(
        usuario_rut_id=profesor_rut
    ).values_list('curso_id_curso_id', flat=True)

    # Unificar los cursos que le corresponden
    cursos = Curso.objects.filter(
        id_curso__in=cursos_directos
    ) | Curso.objects.filter(
        id_curso__in=cursos_asignaturas
    )

    cursos = cursos.distinct().order_by('id_curso')

    # Curso seleccionado desde el formulario
    curso_id = request.GET.get('curso', '').strip()

    curso_seleccionado = None
    alumnos = Alumno.objects.none()

    if curso_id:
        if curso_id.isdigit():
            curso_seleccionado = cursos.filter(
                id_curso=int(curso_id)
            ).first()

        if curso_seleccionado:
            alumnos = Alumno.objects.filter(
                curso_id_curso=curso_seleccionado
            ).select_related(
                'usuario_rut'
            ).order_by('nombre_completo')

        else:
            messages.error(
                request,
                'El curso seleccionado no existe o no está asignado a tu usuario.'
            )

    context = {
        'cursos': cursos,
        'curso_seleccionado': curso_seleccionado,
        'alumnos': alumnos,
        'total_alumnos': alumnos.count()
    }

    return render(
        request,
        'profesor_alumnos.html',
        context
    )


@require_role([2])
def profesor_perfil_alumno(request):
    return render(request, 'profesor_perfil_alumno.html')

# Vistas para el portal de Administrador

@require_role([1])
def admin_inicio(request):
    return render(request, 'admin_inicio.html')

@require_role([1])
def admin_gestion_usuarios(request):
    # Extraemos todos los usuarios y traemos los datos de su rol asociado
    lista_usuarios = Usuario.objects.select_related('rol_id_rol').all()
    
    # Empaquetamos los datos en un "contexto" para mandarlos al HTML
    context = {
        'usuarios': lista_usuarios
    }
    return render(request, 'admin_gestion_usuarios.html', context)

@require_role([1])
def admin_crear_usuario(request):
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

        # 1. Validación de RUT mediante algoritmo Módulo 11
        if not validar_rut(rut_form):
            messages.error(request, 'El RUN ingresado no es válido. Verifique los dígitos e intente nuevamente.')
            return render(request, 'admin_crear_usuario.html')

        # 2. Normalización y formateo con puntos (ej: 19.572.314-1)
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

        # 3. Comprobar si el RUT con formato tradicional ya existe en la BD
        if Usuario.objects.filter(rut=rut_estandar).exists():
            messages.error(request, f'El RUT {rut_estandar} ya se encuentra registrado en el sistema.')
            return render(request, 'admin_crear_usuario.html')

        # 4. Comprobar si el correo ya existe
        if correo_form and Usuario.objects.filter(correo=correo_form.lower()).exists():
            messages.error(request, f'El correo {correo_form} ya pertenece a otro usuario.')
            return render(request, 'admin_crear_usuario.html')

        # Contraseña inicial usando los dígitos del RUT limpio
        password_defecto = rut_limpio

        # 5. Creación y persistencia del usuario en la base de datos
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
                fecha_nacimiento=fecha_nac_form if fecha_nac_form else None
            )

            messages.success(request, 'Usuario creado correctamente con todos sus datos.')
            return redirect('admin_gestion_usuarios')

        except IntegrityError:
            messages.error(request, 'Error de integridad: El usuario o un dato único ya existe en el sistema.')
            return render(request, 'admin_crear_usuario.html')

    return render(request, 'admin_crear_usuario.html')

@require_role([1])
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

    # Obtenemos el usuario o lanzamos 404 si no existe
    usuario = get_object_or_404(Usuario, rut=rut_estandar)

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
                return render(request, 'admin_editar_usuario.html', {'usuario': usuario})

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

            # Al llamar a save(), se ejecutan las reglas del modelo (capitalización, etc.)
            usuario.save()

            messages.success(request, f'Usuario {usuario.rut} actualizado correctamente.')
            return redirect('admin_gestion_usuarios')

        except IntegrityError:
            messages.error(request, 'Error de integridad al intentar actualizar los datos.')
            return render(request, 'admin_editar_usuario.html', {'usuario': usuario})

    return render(request, 'admin_editar_usuario.html', {'usuario': usuario})

@require_role([1])
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

        # El apoderado es opcional por ahora
        apoderado = None

        if apoderado_rut:
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


@require_role([1])
def admin_gestion_incidencias(request):
    return render(request, 'admin_gestion_incidencias.html')

@require_role([1])
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

@require_role([1])
def admin_gestion_inventario(request):
    return render(request, 'admin_gestion_inventario.html')

@require_role([1])
def admin_editar_equipo(request):
    return render(request, 'admin_editar_equipo.html')