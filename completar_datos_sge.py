
import os
import random
from datetime import date

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sge_core.settings")

import django
django.setup()

from django.db import transaction
from sistema.models import Usuario


def generar_telefono(rut):
    rng = random.Random(f"telefono-{rut}")
    return f"+569{rng.randint(10000000, 99999999)}"


def generar_direccion(rut):
    calles = [
        "Los Aromos",
        "Las Acacias",
        "Los Cerezos",
        "Los Pinos",
        "Las Rosas",
        "Los Álamos",
        "Los Copihues",
        "Los Maitenes",
        "Las Araucarias",
        "Los Robles",
        "Las Magnolias",
        "Los Eucaliptos", 
        "Las Camelias",
        "Los Sauces",
        "Las Palmas",
        "Los Olmos",
        "Los Cipreses",  
        "Las Jacarandas",
        "Los Guindos",
        "Las Bugambilias",
        "Los Nogales",
        "Las Higueras", 
        "Los Queules",
        "Las Quillayes",
        "Los Maitenes",
        "Las Lirios",
        "Los Alamos",
    ]

    comunas = [
        "La Pintana",
        "Puente Alto",
        "La Florida",
        "San Bernardo",
        "El Bosque",
        "La Granja",
        "San Ramón",
        "La Cisterna",
        "Pedro Aguirre Cerda",
        "San Joaquín",
        "La Reina",
        "Ñuñoa",
        "Macul",
        "Peñalolén",
        "Santiago",
        "Providencia",
        "Las Condes",
        "Vitacura",
        "Lo Barnechea",
    ]

    rng = random.Random(f"direccion-{rut}")

    calle = rng.choice(calles)
    numero = rng.randint(100, 4500)
    comuna = rng.choice(comunas)

    return f"{calle} {numero}, {comuna}, Santiago"


def generar_fecha_nacimiento(rut):
    rng = random.Random(f"nacimiento-{rut}")

    anio = rng.randint(1960, 1998)
    mes = rng.randint(1, 12)

    if mes == 2:
        dia_maximo = 28
    elif mes in (4, 6, 9, 11):
        dia_maximo = 30
    else:
        dia_maximo = 31

    dia = rng.randint(1, dia_maximo)

    return date(anio, mes, dia)


def correo_faltante(usuario):
    correo = usuario.generar_correo_institucional()

    if correo:
        return correo

    rut_limpio = "".join(
        caracter for caracter in usuario.rut.lower()
        if caracter.isalnum()
    )

    return f"apoderado{rut_limpio}@example.com"


def esta_vacio(valor):
    return valor is None or (
        isinstance(valor, str) and not valor.strip()
    )


def completar_datos():
    print("=" * 55)
    print("COMPLETAR DATOS DE APODERADOS - SGE")
    print("=" * 55)

    apoderados = Usuario.objects.filter(
        rol_id_rol_id=3
    ).order_by("rut")

    total = apoderados.count()
    actualizados = 0
    sin_cambios = 0

    print(f"\nApoderados encontrados: {total}")

    if total == 0:
        print("No se encontraron apoderados.")
        return

    confirmacion = input(
        "\nSe completarán únicamente campos vacíos. "
        "¿Continuar? (S/N): "
    ).strip().lower()

    if confirmacion not in ("s", "si", "sí"):
        print("Operación cancelada. No se modificaron datos.")
        return

    with transaction.atomic():
        for usuario in apoderados:
            cambios = {}

            if esta_vacio(usuario.telefono):
                cambios["telefono"] = generar_telefono(usuario.rut)

            if esta_vacio(usuario.direccion):
                cambios["direccion"] = generar_direccion(usuario.rut)

            if usuario.fecha_nacimiento is None:
                cambios["fecha_nacimiento"] = (
                    generar_fecha_nacimiento(usuario.rut)
                )

            if esta_vacio(usuario.correo):
                cambios["correo"] = correo_faltante(usuario)

            if cambios:
                Usuario.objects.filter(
                    rut=usuario.rut
                ).update(**cambios)

                actualizados += 1

                print(
                    f"Actualizado: {usuario.rut} "
                    f"({', '.join(cambios.keys())})"
                )
            else:
                sin_cambios += 1

    print("\n" + "=" * 55)
    print("RESULTADO FINAL")
    print("=" * 55)
    print(f"Apoderados revisados: {total}")
    print(f"Apoderados actualizados: {actualizados}")
    print(f"Apoderados sin cambios: {sin_cambios}")
    print("\nNo se crearon usuarios ni alumnos.")
    print("No se modificaron tablas ni columnas.")
    print("Proceso finalizado correctamente.")


if __name__ == "__main__":
    completar_datos()
