
import os
import django
import unicodedata

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sge_core.settings")
django.setup()

from django.db import transaction
from sistema.models import Usuario


def limpiar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    ).lower().replace(" ", "")


apoderados = list(
    Usuario.objects.filter(
        rol_id_rol_id=3,
        correo__startswith="apoderado.demo.",
        correo__endswith="@example.com"
    ).order_by("rut")
)

correos_ocupados = {
    correo.lower()
    for correo in Usuario.objects.exclude(
        rut__in=[apoderado.rut for apoderado in apoderados]
    ).exclude(
        correo__isnull=True
    ).values_list("correo", flat=True)
    if correo
}

cambios = []

for apoderado in apoderados:
    nombre = limpiar(apoderado.nombre)
    apellido = limpiar(apoderado.apellido_paterno)

    if not nombre or not apellido:
        continue

    base = f"{nombre[0]}{apellido}"
    correo = f"{base}@santajuliana.cl"
    numero = 2

    while correo.lower() in correos_ocupados:
        correo = f"{base}{numero}@santajuliana.cl"
        numero += 1

    correos_ocupados.add(correo.lower())
    cambios.append((apoderado, correo))


print("Apoderados encontrados:", len(apoderados))
print("Correos preparados:", len(cambios))

for apoderado, correo in cambios[:10]:
    print(apoderado.rut, "->", correo)


respuesta = input(
    "\n¿Confirmas actualizar estos correos? (SI/NO): "
)

if respuesta.strip().upper() == "SI":
    with transaction.atomic():
        for apoderado, correo in cambios:
            apoderado.correo = correo
            apoderado.save(update_fields=["correo"])

    print("Correos actualizados:", len(cambios))
else:
    print("Operacion cancelada. No se modifico MySQL.")
