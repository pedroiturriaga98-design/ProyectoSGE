from django.shortcuts import render

# Vista para el Login
def login_view(request):
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
    return render(request, 'admin_gestion_usuarios.html')

def admin_crear_usuario(request):
    return render(request, 'admin_crear_usuario.html')

def admin_editar_usuario(request):
    return render(request, 'admin_editar_usuario.html')