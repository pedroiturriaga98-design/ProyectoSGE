
import os
import sys

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "sge_core.settings"
)

import django
django.setup()

from django.db import connection
from sistema.models import Alumno, Curso, Calificacion


def existe_tabla(cursor, nombre):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
        """,
        [nombre]
    )
    return cursor.fetchone()[0] > 0


def existe_columna(cursor, tabla, columna):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = %s
          AND COLUMN_NAME = %s
        """,
        [tabla, columna]
    )
    return cursor.fetchone()[0] > 0


def existe_fk(cursor, nombre):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = DATABASE()
          AND CONSTRAINT_NAME = %s
          AND CONSTRAINT_TYPE = 'FOREIGN KEY'
        """,
        [nombre]
    )
    return cursor.fetchone()[0] > 0


def main():
    print("\n===== PREPARACIÓN DE EVALUACIONES SGE =====")

    if connection.vendor != "mysql":
        sys.exit("ERROR: este script requiere MySQL.")

    cursos_antes = Curso.objects.count()
    alumnos_antes = Alumno.objects.count()
    notas_antes = Calificacion.objects.count()

    print("Cursos:", cursos_antes)
    print("Alumnos:", alumnos_antes)
    print("Calificaciones:", notas_antes)

    if notas_antes != 0:
        sys.exit(
            "SEGURIDAD: existen calificaciones. "
            "Se requiere revisar su migración antes de continuar."
        )

    with connection.cursor() as cursor:

        if not existe_tabla(cursor, "evaluacion"):
            cursor.execute(
                """
                CREATE TABLE evaluacion (
                    id_evaluacion INT NOT NULL AUTO_INCREMENT,
                    ASIGNATURA_CURSO_id_asig_curso INT NOT NULL,
                    numero_evaluacion INT NOT NULL,

                    PRIMARY KEY (id_evaluacion),

                    UNIQUE KEY uq_evaluacion_asignatura_numero (
                        ASIGNATURA_CURSO_id_asig_curso,
                        numero_evaluacion
                    ),

                    CONSTRAINT fk_evaluacion_asignatura_curso
                    FOREIGN KEY (
                        ASIGNATURA_CURSO_id_asig_curso
                    )
                    REFERENCES asignatura_curso (
                        id_asig_curso
                    )
                ) ENGINE=InnoDB
                DEFAULT CHARSET=utf8mb3
                """
            )
            print("Tabla evaluacion creada.")
        else:
            print(
                "La tabla evaluacion ya existe. "
                "No se vuelve a crear."
            )

        if not existe_columna(
            cursor,
            "calificacion",
            "EVALUACION_id_evaluacion"
        ):
            cursor.execute(
                """
                ALTER TABLE calificacion
                ADD COLUMN EVALUACION_id_evaluacion
                INT NULL
                """
            )
            print(
                "Columna EVALUACION_id_evaluacion agregada."
            )
        else:
            print("La columna de evaluación ya existe.")

        if not existe_fk(
            cursor,
            "fk_calificacion_evaluacion"
        ):
            cursor.execute(
                """
                ALTER TABLE calificacion
                ADD CONSTRAINT fk_calificacion_evaluacion
                FOREIGN KEY (
                    EVALUACION_id_evaluacion
                )
                REFERENCES evaluacion (
                    id_evaluacion
                )
                """
            )
            print("Relación con evaluacion creada.")
        else:
            print("La relación ya existe.")

    print("\n===== VERIFICACIÓN FINAL =====")

    print("Cursos:", Curso.objects.count())
    print("Alumnos:", Alumno.objects.count())
    print("Calificaciones:", Calificacion.objects.count())

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM evaluacion
            """
        )
        print("Evaluaciones:", cursor.fetchone()[0])

        cursor.execute("SHOW COLUMNS FROM calificacion")
        print("\nColumnas de calificacion:")
        for columna in cursor.fetchall():
            print("-", columna[0])

    print("\nPreparación finalizada.")


if __name__ == "__main__":
    main()
