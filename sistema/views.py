from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from functools import wraps # Importante para hacer decoradores
from .models import Usuario

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
    return render(request, 'profesor_alumnos.html')

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
        rut_form = request.POST.get('rut')
        rol_id = request.POST.get('rol_id_rol') # Minúsculas
        nombre_form = request.POST.get('nombre')
        correo_form = request.POST.get('correo')
        ap_paterno_form = request.POST.get('apellido_paterno')
        ap_materno_form = request.POST.get('apellido_materno')
        telefono_form = request.POST.get('telefono')
        direccion_form = request.POST.get('direccion')
        fecha_nac_form = request.POST.get('fecha_nacimiento')
        
        # Contraseña inicial usando el RUT
        password_defecto = rut_form.replace("-", "").replace(".", "")

        # Guardamos en la base de datos
        Usuario.objects.create(
            rut=rut_form,
            password_hash=password_defecto,
            rol_id_rol_id=rol_id, # Django le agrega automáticamente el _id al final
            nombre=nombre_form,
            correo=correo_form,
            apellido_paterno=ap_paterno_form,
            apellido_materno=ap_materno_form,
            telefono=telefono_form,
            direccion=direccion_form,
            fecha_nacimiento=fecha_nac_form if fecha_nac_form else None
        )
        
        messages.success(request, 'Usuario creado correctamente con todos sus datos.')
        return redirect('admin_gestion_usuarios') 

    return render(request, 'admin_crear_usuario.html')

@require_role([1])
def admin_editar_usuario(request, rut):
    # 1. Buscamos al usuario en la BD usando el RUT
    usuario = get_object_or_404(Usuario, rut=rut)

    # 2. Si el formulario se envió (alguien apretó "Actualizar Usuario")
    if request.method == 'POST':
        usuario.nombre = request.POST.get('nombre')
        usuario.apellido_paterno = request.POST.get('apellido_paterno')
        usuario.apellido_materno = request.POST.get('apellido_materno')
        usuario.correo = request.POST.get('correo')
        usuario.telefono = request.POST.get('telefono')
        usuario.direccion = request.POST.get('direccion')
        
        # Validamos si mandó fecha (a veces los navegadores la mandan vacía)
        fecha_nac_form = request.POST.get('fecha_nacimiento')
        if fecha_nac_form:
            usuario.fecha_nacimiento = fecha_nac_form
            
        usuario.rol_id_rol_id = request.POST.get('rol_id_rol')
        
        # Opcional: Podrías manejar el estado activo/inactivo aquí si lo agregaste a tu BD
        
        # Guardamos en la base de datos
        usuario.save()
        
        # Redirigimos a la tabla principal
        return redirect('admin_gestion_usuarios')

    # 3. Si alguien solo entró a la página a mirar, le mostramos el HTML
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
    return render(request, 'admin_alumnos.html')

@require_role([1])
def admin_editar_alumno(request, rut):
    return render(request, 'admin_editar_alumno.html')

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