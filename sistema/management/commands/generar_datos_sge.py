
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth.hashers import make_password

from sistema.models import Alumno, Curso, Usuario, Rol


META_POR_CURSO = 30

NOMBRES = [
    "Sofia", "Mateo", "Valentina", "Benjamin", "Isidora",
    "Tomas", "Emilia", "Vicente", "Florencia", "Agustin",
    "Catalina", "Martin", "Antonia", "Joaquin", "Josefa",
    "Lucas", "Trinidad", "Maximiliano", "Amanda", "Diego",
]

APELLIDOS = [
    "Gonzalez", "Munoz", "Rojas", "Diaz", "Perez",
    "Soto", "Contreras", "Silva", "Martinez", "Sepulveda",
    "Morales", "Rodriguez", "Lopez", "Fuentes", "Torres",
]


def generar_rut(numero):
    """Genera un RUT con digito verificador matematicamente valido."""
    digitos = str(numero)
    suma = 0
    factor = 2

    for digito in reversed(digitos):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1

    resultado = 11 - (suma % 11)

    if resultado == 11:
        dv = "0"
    elif resultado == 10:
        dv = "K"
    else:
        dv = str(resultado)

    return f"{numero:,}".replace(",", ".") + "-" + dv


class Command(BaseCommand):
    help = "Completa cada curso hasta 30 alumnos ficticios y crea apoderados compartidos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma la escritura en la base de datos.",
        )

    def handle(self, *args, **options):
        cursos = list(Curso.objects.order_by("id_curso"))

        if len(cursos) != 28:
            raise CommandError(
                f"Se esperaban 28 cursos, pero existen {len(cursos)}. "
                "No se modifico ningun registro."
            )

        if not Rol.objects.filter(id_rol=3).exists():
            raise CommandError(
                "No existe el rol de apoderado con id_rol=3."
            )

        # Validamos los campos esenciales antes de escribir.
        for modelo, campos in [
            (Usuario, ["rut", "password_hash", "rol_id_rol", "nombre"]),
            (Alumno, [
                "rut_alumno", "nombre_completo", "estado_matricula",
                "curso_id_curso", "usuario_rut",
            ]),
        ]:
            disponibles = {campo.name for campo in modelo._meta.fields}
            faltantes = set(campos) - disponibles
            if faltantes:
                raise CommandError(
                    f"Faltan campos en {modelo.__name__}: {faltantes}"
                )

        existentes = {
            curso.id_curso: Alumno.objects.filter(
                curso_id_curso=curso
            ).count()
            for curso in cursos
        }

        pendientes = sum(
            max(0, META_POR_CURSO - existentes[curso.id_curso])
            for curso in cursos
        )

        self.stdout.write(
            f"Cursos: {len(cursos)} | "
            f"Alumnos existentes: {sum(existentes.values())} | "
            f"Alumnos por crear: {pendientes}"
        )

        if not options["confirmar"]:
            self.stdout.write(
                self.style.WARNING(
                    "Simulacion: no se modifico la base de datos. "
                    "Ejecuta con --confirmar para crear los registros."
                )
            )
            return

        alumnos_creados = 0
        apoderados_creados = 0
        "password_hash": make_password(rut_apoderado)

        # Rangos reservados para este conjunto de pruebas.
        # Cada curso tiene hasta 1000 posiciones disponibles.
        # Los RUT generados son ficticios, pero su DV es valido.
        with transaction.atomic():
            for indice_curso, curso in enumerate(cursos):
                faltantes = max(
                    0, META_POR_CURSO - existentes[curso.id_curso]
                )

                creados_en_curso = 0

                for posicion in range(1, 1001):
                    if creados_en_curso >= faltantes:
                        break

                    numero_alumno = (
                        30000000 + indice_curso * 1000 + posicion
                    )
                    rut_alumno = generar_rut(numero_alumno)

                    # Evitar sobrescribir cualquier alumno existente.
                    if Alumno.objects.filter(
                        rut_alumno=rut_alumno
                    ).exists():
                        continue

                    # Cada pareja de cursos comparte apoderados.
                    # El mismo apoderado se usa para la misma
                    # posicion en ambos cursos de la pareja.
                    grupo_cursos = indice_curso // 2
                    numero_apoderado = (
                        40000000 + grupo_cursos * 1000 + posicion
                    )
                    rut_apoderado = generar_rut(numero_apoderado)

                    apellido = APELLIDOS[
                        (grupo_cursos + posicion) % len(APELLIDOS)
                    ]
                    segundo_apellido = APELLIDOS[
                        (grupo_cursos + posicion + 5) % len(APELLIDOS)
                    ]

                    nombre_apoderado = NOMBRES[
                        (grupo_cursos + posicion + 3) % len(NOMBRES)
                    ]

                    apoderado, creado = Usuario.objects.get_or_create(
                        rut=rut_apoderado,
                        defaults={
                            "nombre": nombre_apoderado,
                            "apellido_paterno": apellido,
                            "apellido_materno": segundo_apellido,
                            "correo": (
                                f"apoderado.demo."
                                f"{numero_apoderado}@example.com"
                            ),
                            "password_hash": clave_hash,
                            "rol_id_rol_id": 3,
                        },
                    )

                    # No vincular alumnos a un usuario de otro rol.
                    if apoderado.rol_id_rol_id != 3:
                        raise CommandError(
                            f"El RUT {rut_apoderado} pertenece "
                            "a un usuario que no es apoderado."
                        )

                    if creado:
                        apoderados_creados += 1

                    nombre_alumno = NOMBRES[
                        (indice_curso + posicion) % len(NOMBRES)
                    ]

                    Alumno.objects.create(
                        rut_alumno=rut_alumno,
                        nombre_completo=(
                            f"{nombre_alumno} "
                            f"{apellido} {segundo_apellido}"
                        ),
                        estado_matricula="Activo",
                        curso_id_curso=curso,
                        usuario_rut=apoderado,
                    )

                    creados_en_curso += 1
                    alumnos_creados += 1

                if creados_en_curso != faltantes:
                    raise CommandError(
                        f"No fue posible completar {curso.nombre_curso}."
                    )

                self.stdout.write(
                    f"{curso.nombre_curso}: "
                    f"+{creados_en_curso} alumnos"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Carga terminada. "
                f"Alumnos nuevos: {alumnos_creados}. "
                f"Apoderados nuevos: {apoderados_creados}."
            )
        )
