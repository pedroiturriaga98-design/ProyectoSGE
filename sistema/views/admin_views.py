from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q, Max
from django.db import transaction, IntegrityError
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from sistema.models import (
    Usuario,
    Rol,
    Alumno,
    Curso,
    SolicitudInsumo,
    TicketSoporte,
    AsignaturaCurso,
    DetalleInsumo,
    Evaluacion,
    Asignatura,
    EquipoTi
)
from .auth_views import require_role, validar_rut


@require_role([1, 4])
def admin_inicio(request):
    return render(request, 'admin_inicio.html')


@require_role([1, 4])
def admin_gestion_usuarios(request):
    lista_usuarios = Usuario.objects.select_related('rol_id_rol').all().order_by('apellido_paterno', 'nombre')
    
    query = request.GET.get('q', '').strip()
    rol_filtro = request.GET.get('rol', '').strip()

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

    if rol_filtro:
        lista_usuarios = lista_usuarios.filter(rol_id_rol_id=rol_filtro)

    roles = Rol.objects.all()

    paginator = Paginator(lista_usuarios, 10)
    page_number = request.GET.get('page')
    usuarios = paginator.get_page(page_number)

    context = {
        'usuarios': usuarios,
        'roles': roles,
        'query': query,
        'rol_filtro': rol_filtro,
    }
    return render(request, 'admin_gestion_usuarios.html', context)


@require_role([1, 4])
def admin_crear_usuario(request):
    roles = Rol.objects.all()

    if request.method == 'POST':
        rut_form = request.POST.get('rut', '').strip()
        rol_id = request.POST.get('rol_id_rol')
        nombre_form = request.POST.get('nombre', '').strip()
        correo_form = request.POST.get('correo', '').strip()
        ap_paterno_form = request.POST.get('apellido_paterno', '').strip()
        ap_materno_form = request.POST.get('apellido_materno', '').strip()
        telefono_form = request.POST.get('telefono', '').strip()
        direccion_form = request.POST.get('direccion', '').strip()
        fecha_nac_form = request.POST.get('fecha_nacimiento')

        if not validar_rut(rut_form):
            messages.error(request, 'El RUN ingresado no es válido. Verifique los dígitos e intente nuevamente.')
            return render(request, 'admin_crear_usuario.html', {'roles': roles})

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

        if Usuario.objects.filter(rut=rut_estandar).exists():
            messages.error(request, f'El RUT {rut_estandar} ya se encuentra registrado en el sistema.')
            return render(request, 'admin_crear_usuario.html', {'roles': roles})

        if correo_form and Usuario.objects.filter(correo=correo_form.lower()).exists():
            messages.error(request, f'El correo {correo_form} ya pertenece a otro usuario.')
            return render(request, 'admin_crear_usuario.html', {'roles': roles})

        password_defecto = make_password(rut_limpio)

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

    return render(request, 'admin_crear_usuario.html', {'roles': roles})


@require_role([1, 4])
def admin_editar_usuario(request, rut):
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

    usuario = get_object_or_404(Usuario, rut=rut_estandar)
    roles = Rol.objects.all().order_by('id_rol')

    if request.method == 'POST':
        nombre_form = request.POST.get('nombre', '').strip()
        ap_paterno_form = request.POST.get('apellido_paterno', '').strip()
        ap_materno_form = request.POST.get('apellido_materno', '').strip()
        correo_form = request.POST.get('correo', '').strip()
        rol_id = request.POST.get('rol_id_rol')
        telefono_form = request.POST.get('telefono', '').strip()
        direccion_form = request.POST.get('direccion', '').strip()
        fecha_nac_form = request.POST.get('fecha_nacimiento')

        if correo_form:
            correo_lower = correo_form.lower()
            existe_correo = Usuario.objects.filter(correo=correo_lower).exclude(rut=usuario.rut).exists()
            if existe_correo:
                messages.error(request, f'El correo {correo_form} ya pertenece a otro usuario registrado.')
                return render(request, 'admin_editar_usuario.html', {'usuario': usuario, 'roles': roles})

        try:
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


@require_role([1, 4])
def admin_eliminar_usuario(request, rut):
    usuario = get_object_or_404(Usuario, rut=rut)
    rut_actual = request.session.get('usuario_rut')

    if usuario.rut == rut_actual:
        messages.error(request, 'No puedes eliminar tu propia cuenta activa.')
        return redirect('admin_gestion_usuarios')

    try:
        with transaction.atomic():
            AsignaturaCurso.objects.filter(usuario_rut=usuario).delete()
            Curso.objects.filter(usuario_rut=usuario).update(usuario_rut_id=rut_actual)

            solicitudes_ids = SolicitudInsumo.objects.filter(usuario_rut=usuario).values_list('id_solicitud', flat=True)
            DetalleInsumo.objects.filter(solicitud_insumo_id_solicitud__in=solicitudes_ids).delete()
            SolicitudInsumo.objects.filter(usuario_rut=usuario).delete()
            TicketSoporte.objects.filter(usuario_rut=usuario).delete()

            usuario.delete()
            messages.success(request, f'Usuario {usuario.nombre} {usuario.apellido_paterno} eliminado correctamente.')
    except IntegrityError:
        usuario.activo = 0
        usuario.save()
        messages.warning(
            request,
            f'El usuario tiene registros históricos inalterables. Su cuenta fue cambiada a estado Inactivo.'
        )

    return redirect('admin_gestion_usuarios')


@require_role([1, 4])
def admin_alumnos(request):
    alumnos_qs = Alumno.objects.select_related(
        'curso_id_curso'
    ).order_by('nombre_completo')

    cursos = Curso.objects.all().order_by('id_curso')

    query = request.GET.get('q', '').strip()
    curso_seleccionado = request.GET.get('curso', '').strip()

    if query:
        palabras = query.split()
        for palabra in palabras:
            alumnos_qs = alumnos_qs.filter(
                Q(nombre_completo__icontains=palabra) |
                Q(rut_alumno__icontains=palabra)
            )

    if curso_seleccionado:
        alumnos_qs = alumnos_qs.filter(
            curso_id_curso_id=curso_seleccionado
        )

    paginator = Paginator(alumnos_qs, 10)
    page_number = request.GET.get('page')
    alumnos_paginados = paginator.get_page(page_number)

    lista_alumnos_procesada = []
    for alumno in alumnos_paginados:
        alumno.nombre_apoderado_str = None
        
        if hasattr(alumno, 'usuario_rut') and alumno.usuario_rut:
            if isinstance(alumno.usuario_rut, Usuario):
                alumno.nombre_apoderado_str = f"{alumno.usuario_rut.nombre} {alumno.usuario_rut.apellido_paterno}"
            else:
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

        if not validar_rut(rut_form):
            messages.error(request, 'El RUT del alumno no es válido.')
            return render(request, 'admin_crear_alumno.html', context)

        rut_limpio = rut_form.replace('.', '').replace('-', '').upper()
        cuerpo = rut_limpio[:-1]
        dv = rut_limpio[-1]

        rut_estandar = f"{int(cuerpo):,}".replace(',', '.') + '-' + dv

        if Alumno.objects.filter(rut_alumno=rut_estandar).exists():
            messages.error(request, 'Este alumno ya está registrado.')
            return render(request, 'admin_crear_alumno.html', context)

        if not nombre:
            messages.error(request, 'Debes ingresar el nombre completo.')
            return render(request, 'admin_crear_alumno.html', context)

        curso = Curso.objects.filter(id_curso=curso_id).first() if curso_id.isdigit() else None

        if curso is None:
            messages.error(request, 'Debes seleccionar un curso válido.')
            return render(request, 'admin_crear_alumno.html', context)

        if estado not in ['Activo', 'Inactivo']:
            messages.error(request, 'Selecciona un estado de matrícula válido.')
            return render(request, 'admin_crear_alumno.html', context)

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
    alumno = get_object_or_404(
        Alumno.objects.select_related(
            'curso_id_curso',
            'usuario_rut'
        ),
        rut_alumno=rut
    )

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

        context['datos'] = request.POST

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
            alumno.nombre_completo = nombre
            alumno.curso_id_curso = curso
            alumno.estado_matricula = estado
            alumno.usuario_rut = apoderado

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
    lista_incidencias = TicketSoporte.objects.all().order_by('-fecha_reporte', '-id_ticket')
    
    query = request.GET.get('q', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()
    prioridad_filtro = request.GET.get('prioridad', '').strip()

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

    paginator = Paginator(lista_incidencias, 10)
    page_number = request.GET.get('page')
    incidencias = paginator.get_page(page_number)

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


@require_role([1, 4])
def admin_solicitudes_material(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    solicitudes = SolicitudInsumo.objects.filter(tipo_solicitud='Solicitud de Material').order_by('-fecha')
    
    context = {
        'solicitudes': solicitudes,
        'titulo': 'Solicitudes de Material (Aseo)'
    }
    return render(request, 'admin_gestion_solicitudes.html', context)


@require_role([1, 4])
def admin_solicitudes_reposicion(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    solicitudes = SolicitudInsumo.objects.filter(tipo_solicitud='Solicitud de Reposición').order_by('-fecha')
    
    context = {
        'solicitudes': solicitudes,
        'titulo': 'Solicitudes de Reposición (Aseo)'
    }
    return render(request, 'admin_gestion_solicitudes.html', context)


@require_role([1, 4])
def admin_gestion_profesores(request):
    query = request.GET.get('q', '').strip()
    asignatura_filtro = request.GET.get('asignatura', '').strip()
    estado_filtro = request.GET.get('estado', '').strip()

    profesores_qs = Usuario.objects.filter(rol_id_rol_id=2).order_by('apellido_paterno', 'nombre')

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

    paginator = Paginator(profesores_qs, 10)
    page_number = request.GET.get('page')
    pagina_profesores = paginator.get_page(page_number)

    lista_profesores = []
    for p in pagina_profesores:
        partes_iniciales = f"{(p.nombre or '')[:1]}{(p.apellido_paterno or '')[:1]}".upper()
        p.iniciales = partes_iniciales if partes_iniciales else "PR"
        
        p.jefaturas = Curso.objects.filter(usuario_rut=p)
        
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

        if es_jefe:
            Curso.objects.filter(id_curso=curso_obj.id_curso).update(usuario_rut=profesor_obj)

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


@require_role([1, 4])
def admin_gestion_apoderados(request):
    query = request.GET.get('q', '').strip()
    
    try:
        apoderados_qs = Usuario.objects.filter(rol_id_rol_id=3).order_by('apellido_paterno', 'nombre')
    except Exception:
        apoderados_qs = Usuario.objects.filter(rol_id_rol=3).order_by('apellido_paterno', 'nombre')

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

    paginator = Paginator(apoderados_qs, 10)
    page_number = request.GET.get('page')
    apoderados_paginados = paginator.get_page(page_number)

    lista_procesada = []
    for apo in apoderados_paginados:
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
    apoderado = get_object_or_404(Usuario, rut=rut)
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


@require_role([1, 4])
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
                        prioridad=prioridad,
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