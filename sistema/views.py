from django.shortcuts import render

# Vista para el Login
def login_view(request):
    return render(request, 'login.html')

# Vistas para el portal de apoderados
def apoderado_notas(request):
    return render(request, 'apoderado_notas.html')

def apoderado_asistencia(request):
    return render(request, 'apoderado_asistencia.html')

def apoderado_calendario(request):
    return render(request, 'apoderado_calendario.html')

def apoderado_certificados(request):
    return render(request, 'apoderado_certificados.html')