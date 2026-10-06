from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('apoderado/notas/', views.apoderado_notas, name='apoderado_notas'),
    path('apoderado/asistencia/', views.apoderado_asistencia, name='apoderado_asistencia'),
    path('apoderado/calendario/', views.apoderado_calendario, name='apoderado_calendario'),
    path('apoderado/certificados/', views.apoderado_certificados, name='apoderado_certificados'),
]