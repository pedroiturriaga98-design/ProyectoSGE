from django.shortcuts import render, redirect
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
    return render(request, 'admin_crear_usuario.html')

def admin_editar_usuario(request):
    return render(request, 'admin_editar_usuario.html')

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