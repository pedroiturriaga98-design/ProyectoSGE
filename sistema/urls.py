from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    # Rutas para el Portal de apoderado
    path('apoderado/', views.apoderado_inicio, name='apoderado_inicio'),
    path('apoderado/notas/', views.apoderado_notas, name='apoderado_notas'),
    path('apoderado/asistencia/', views.apoderado_asistencia, name='apoderado_asistencia'),
    path('apoderado/calendario/', views.apoderado_calendario, name='apoderado_calendario'),
    path('apoderado/certificados/', views.apoderado_certificados, name='apoderado_certificados'),
    # Rutas para el Portal de Profesores
    path('profesor/', views.profesor_inicio, name='profesor_inicio'),
    path('profesor/notas/', views.profesor_notas, name='profesor_notas'),
    path('profesor/asistencia/', views.profesor_asistencia, name='profesor_asistencia'),
    path('profesor/incidencias/agregar/', views.profesor_agregar_incidencia, name='profesor_agregar_incidencia'),
    path('profesor/incidencias/revisar/', views.profesor_revisar_incidencias, name='profesor_revisar_incidencias'),
    path('profesor/alumnos/', views.profesor_alumnos, name='profesor_alumnos'),
    path('profesor/alumnos/perfil/', views.profesor_perfil_alumno, name='profesor_perfil_alumno'),





]