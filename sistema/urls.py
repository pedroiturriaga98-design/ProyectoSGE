from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Autenticación y Cuenta
    path('', views.login_view, name='login'),
    path('cambiar-password/', views.cambiar_password_obligatorio, name='cambiar_password_obligatorio'),
    path('mi-cuenta/cambiar-password/', views.cambiar_password_perfil, name='cambiar_password_perfil'),
    path('recuperar-contrasena/', views.recuperar_contrasena, name='recuperar_contrasena'),
    path('password_reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset_form.html'), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),

    # Portal Apoderado
    path('apoderado/', views.apoderado_inicio, name='apoderado_inicio'),
    path('apoderado/notas/', views.apoderado_notas, name='apoderado_notas'),
    path('apoderado/asistencia/', views.apoderado_asistencia, name='apoderado_asistencia'),
    path('apoderado/calendario/', views.apoderado_calendario, name='apoderado_calendario'),
    path('apoderado/calendario/eventos/', views.apoderado_calendario_eventos, name='apoderado_calendario_eventos'),
    path('apoderado/certificados/', views.apoderado_certificados, name='apoderado_certificados'),
    path('apoderado/certificados/descargar/', views.apoderado_descargar_certificado, name='apoderado_descargar_certificado'),

    # Portal Profesor
    path('profesor/', views.profesor_inicio, name='profesor_inicio'),
    path('profesor/notas/', views.profesor_notas, name='profesor_notas'),
    path('profesor/asistencia/', views.profesor_asistencia, name='profesor_asistencia'),
    path('profesor/alumnos/', views.profesor_alumnos, name='profesor_alumnos'),
    path('profesor/alumnos/perfil/<str:rut>/', views.profesor_perfil_alumno, name='profesor_perfil_alumno'),
    path('profesor/incidencias/', views.profesor_gestion_incidencias, name='profesor_gestion_incidencias'),
    path('profesor/incidencias/agregar/', views.profesor_agregar_incidencia, name='profesor_agregar_incidencia'),
    path('profesor/incidencias/detalle/<int:pk>/', views.profesor_detalle_incidencia, name='profesor_detalle_incidencia'),
    path('profesor/calendario/', views.profesor_calendario, name='profesor_calendario'),
    path('profesor/calendario/eventos/', views.profesor_calendario_eventos, name='profesor_calendario_eventos'),
    path('profesor/calendario/guardar/', views.profesor_calendario_guardar, name='profesor_calendario_guardar'),
    path('profesor/calendario/eliminar/', views.profesor_calendario_eliminar, name='profesor_calendario_eliminar'),

    # Administración General (Usuarios, Alumnos, Profesores y Apoderados)
    path('administrador/', views.admin_inicio, name='admin_inicio'),
    path('administrador/usuarios/', views.admin_gestion_usuarios, name='admin_gestion_usuarios'),
    path('administrador/usuarios/crear/', views.admin_crear_usuario, name='admin_crear_usuario'),
    path('administrador/usuarios/editar/<str:rut>/', views.admin_editar_usuario, name='admin_editar_usuario'),
    path('administrador/usuarios/eliminar/<str:rut>/', views.admin_eliminar_usuario, name='admin_eliminar_usuario'),
    path('administrador/alumnos/', views.admin_alumnos, name='admin_alumnos'),
    path('administrador/alumnos/crear/', views.admin_crear_alumno, name='admin_crear_alumno'),
    path('administrador/alumnos/editar/<str:rut>/', views.admin_editar_alumno, name='admin_editar_alumno'),
    path('administrador/profesores/', views.admin_gestion_profesores, name='admin_gestion_profesores'),
    path('administrador/profesores/editar/', views.admin_editar_profesor, name='admin_editar_profesor'),
    path('administrador/profesores/editar/<str:rut>/', views.admin_editar_profesor, name='admin_editar_profesor'),
    path('administrador/apoderados/', views.admin_gestion_apoderados, name='admin_gestion_apoderados'),
    path('administrador/apoderados/editar/', views.admin_editar_apoderado, name='admin_editar_apoderado'),
    path('administrador/apoderados/editar/<str:rut>/', views.admin_editar_apoderado, name='admin_editar_apoderado'),
    path('apoderados/editar/<str:rut>/', views.admin_editar_apoderado, name='admin_editar_apoderado'),

    # Gestión TI (Incidencias e Inventario TI)
    path('administrador/incidencias/', views.admin_gestion_incidencias, name='admin_gestion_incidencias'),
    path('administrador/incidencias/crear/', views.admin_crear_incidencia, name='admin_crear_incidencia'),
    path('administrador/incidencias/editar/<int:pk>/', views.admin_editar_incidencia, name='admin_editar_incidencia'),
    path('administrador/incidencias/detalle/<int:pk>/', views.admin_detalle_incidencia, name='admin_detalle_incidencia'),
    path('administrador/inventario/', views.inventario_ti, name='admin_gestion_inventario'),
    path('administrador/inventario/equipo/', views.admin_editar_equipo, name='admin_editar_equipo'),
    path('inventario/ti/', views.inventario_ti, name='inventario_ti'),
    path('inventario/ti/crear/', views.crear_equipo_ti, name='crear_equipo_ti'),
    path('inventario-ti/editar/<str:codigo>/', views.admin_editar_equipo, name='admin_editar_equipo'),

    # Gestión Aseo e Insumos (Administrador y Personal de Aseo)
    path('aseo/inicio/', views.inicio_supervisor_aseo, name='inicio_supervisor_aseo'),
    path('aseo/incidencias/', views.incidencias_aseo, name='incidencias_aseo'),
    path('aseo/incidencias/crear/', views.crear_incidencia_aseo, name='crear_incidencia_aseo'),
    path('aseo/solicitudes/resolver/<int:id_solicitud>/', views.resolver_solicitud_aseo, name='resolver_solicitud_aseo'),
    path('inventario/aseo/', views.inventario_aseo, name='inventario_aseo'),
    path('inventario/aseo/crear/', views.crear_insumo_aseo, name='crear_insumo_aseo'),
    path('aseo/inventario/ajustar/<int:id_insumo>/', views.ajustar_stock_insumo, name='ajustar_stock_insumo'),
    path('aseo/inventario/retirar/<int:id_insumo>/', views.retirar_stock_aseo, name='retirar_stock_aseo'),
    path('personal-aseo/incidencias/', views.incidencias_personal_aseo, name='incidencias_personal_aseo'),
    path('personal-aseo/inventario/', views.inventario_personal_aseo, name='inventario_personal_aseo'),
    path('admin/solicitudes/material/', views.admin_solicitudes_material, name='admin_solicitudes_material'),
    path('admin/solicitudes/reposicion/', views.admin_solicitudes_reposicion, name='admin_solicitudes_reposicion'),
]