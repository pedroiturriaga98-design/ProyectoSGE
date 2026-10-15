@echo off
echo Cargando datos en tu MySQL local...
python manage.py loaddata datos_iniciales.json
echo ¡Base de datos actualizada con exito!