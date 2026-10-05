from django.contrib import admin
from django.apps import apps

# Traemos todos los modelos que Django generó en tu app 'sistema'
modelos_sistema = apps.get_app_config('sistema').get_models()

# Registramos solo los modelos del colegio, filtrando los internos de Django
for modelo in modelos_sistema:
    if not modelo.__name__.startswith(('Auth', 'Django')):
        try:
            admin.site.register(modelo)
        except admin.sites.AlreadyRegistered:
            pass