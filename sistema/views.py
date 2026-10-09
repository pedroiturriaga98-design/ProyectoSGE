from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Usuario # Importamos tu tabla de usuarios

# Vista para el Login (Actualizada con lógica de validación)
def login_view(request):
    if request.method == 'POST':
        # Capturamos lo que el usuario escribió en el HTML
        rut_ingresado = request.POST.get('username') 
        password_ingresada = request.POST.get('password')

        try:
            # 1. Buscamos al usuario en la base de datos
            usuario = Usuario.objects.get(rut=rut_ingresado)

            # 2. Comparamos la contraseña 
            if usuario.password_hash == password_ingresada:
                
                # 3. Guardamos su sesión (el "ticket" del navegador)
                request.session['usuario_rut'] = usuario.rut
                request.session['rol_id'] = usuario.rol_id_rol.id_rol

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
            messages.error(request, 'El usuario ingresado no existe en el sistema.')

    # Si entra por primera vez (GET), muestra la página normal
    return render(request, 'login.html')


# Vistas para el portal de apoderados

def apoderado_inicio(request):
    return render(request, 'apoderado_inicio.html')

def apoderado_notas(request):
    return render(request, 'apoderado_notas.html')

def apoderado_asistencia(request):
    return render(request, 'apoderado_asistencia.html')

def apoderado_calendario(request):
    return render(request, 'apoderado_calendario.html')

def apoderado_certificados(request):
    return render(request, 'apoderado_certificados.html')

# Vistas para el portal de Profesores
def profesor_inicio(request):
    return render(request, 'profesor_inicio.html')

def profesor_notas(request):
    return render(request, 'profesor_notas.html')

def profesor_asistencia(request):
    return render(request, 'profesor_asistencia.html')

def profesor_agregar_incidencia(request):
    return render(request, 'profesor_agregar_incidencia.html')

def profesor_revisar_incidencias(request):
    return render(request, 'profesor_revisar_incidencias.html')

def profesor_alumnos(request):
    return render(request, 'profesor_alumnos.html')

def profesor_perfil_alumno(request):
    return render(request, 'profesor_perfil_alumno.html')

# Vistas para el portal de Administrador

def admin_inicio(request):
    return render(request, 'admin_inicio.html')

def admin_gestion_usuarios(request):
    # Extraemos todos los usuarios y traemos los datos de su rol asociado
    lista_usuarios = Usuario.objects.select_related('rol_id_rol').all()
    
    # Empaquetamos los datos en un "contexto" para mandarlos al HTML
    context = {
        'usuarios': lista_usuarios
    }
    return render(request, 'admin_gestion_usuarios.html', context)

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

def admin_alumnos(request):
    return render(request, 'admin_alumnos.html')

def admin_editar_alumno(request):
    return render(request, 'admin_editar_alumno.html')

def admin_gestion_incidencias(request):
    return render(request, 'admin_gestion_incidencias.html')

def admin_editar_incidencia(request):
    return render(request, 'admin_editar_incidencia.html')

def admin_gestion_apoderados(request):
    return render(request, 'admin_gestion_apoderados.html')

def admin_editar_apoderado(request):
    return render(request, 'admin_editar_apoderado.html')

def admin_gestion_profesores(request):
    return render(request, 'admin_gestion_profesores.html')

def admin_editar_profesor(request):
    return render(request, 'admin_editar_profesor.html')

def admin_gestion_inventario(request):
    return render(request, 'admin_gestion_inventario.html')

def admin_editar_equipo(request):
    return render(request, 'admin_editar_equipo.html')