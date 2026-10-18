"""Carga idempotente de asignaturas y relaciones con los 28 cursos del SGE.
Ejecutar desde la raíz del proyecto: python cargar_asignaturas_sge.py
No modifica alumnos, apoderados ni calificaciones.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sge_core.settings')
django.setup()

from django.db import transaction
from sistema.models import Curso, Asignatura, AsignaturaCurso

BASICA = [
    'Lenguaje y Comunicación', 'Matemática', 'Ciencias Naturales',
    'Historia, Geografía y Ciencias Sociales', 'Inglés',
    'Educación Física y Salud', 'Artes Visuales', 'Música',
    'Tecnología', 'Orientación', 'Religión',
]
MEDIA_1_2 = [
    'Lengua y Literatura', 'Matemática', 'Biología', 'Física',
    'Química', 'Historia, Geografía y Ciencias Sociales', 'Inglés',
    'Educación Física y Salud', 'Tecnología', 'Orientación',
]
MEDIA_3_4 = [
    'Lengua y Literatura', 'Matemática', 'Educación Ciudadana',
    'Filosofía', 'Ciencias para la Ciudadanía', 'Inglés',
]
ESPECIALIDADES = {
    'A': ['Probabilidades y Estadística', 'Geografía y Problemas Ambientales',
          'Participación y Argumentación en Democracia'],
    'B': ['Preparación de insumos y equipos de cocina',
          'Elaboración de platos calientes y fríos', 'Pastelería y repostería'],
    'C': ['Cálculo y registro de remuneraciones (sueldos)',
          'Contabilidad básica y sistemas contables',
          'Emprendimiento y empleabilidad'],
}

def asignaturas_para_curso(curso):
    nombre = curso.nombre_curso.strip()
    partes = nombre.split()
    if len(partes) != 3 or partes[2] not in ('A', 'B', 'C'):
        raise ValueError(f'Nombre de curso inesperado: {nombre!r}')
    nivel, etapa, letra = partes
    numero = int(nivel.replace('°', ''))
    if etapa == 'Básico' and 1 <= numero <= 8 and letra in ('A', 'B'):
        return BASICA
    if etapa == 'Medio' and numero in (1, 2):
        return MEDIA_1_2
    if etapa == 'Medio' and numero in (3, 4):
        return MEDIA_3_4 + ESPECIALIDADES[letra]
    raise ValueError(f'Curso fuera del plan: {nombre!r}')

def main():
    cursos = list(Curso.objects.all().order_by('id_curso'))
    if len(cursos) != 28:
        raise ValueError(f'Se esperaban 28 cursos; se encontraron {len(cursos)}. No se realizaron cambios.')
    planes = [(curso, asignaturas_para_curso(curso)) for curso in cursos]
    if sum(len(materias) for _, materias in planes) != 290:
        raise ValueError('El total de relaciones esperadas no es 290.')
    if any(not curso.usuario_rut_id for curso in cursos):
        raise ValueError('Hay cursos sin profesor asociado. No se realizaron cambios.')

    nombres = list(dict.fromkeys(nombre for _, materias in planes for nombre in materias))
    if Asignatura.objects.filter(nombre_asignatura__in=nombres).values('nombre_asignatura').distinct().count() != Asignatura.objects.filter(nombre_asignatura__in=nombres).count():
        raise ValueError('Hay nombres de asignatura duplicados en la base. Revisar antes de continuar.')

    creadas = 0
    relaciones_creadas = 0
    with transaction.atomic():
        asignaturas = {a.nombre_asignatura: a for a in Asignatura.objects.all()}
        siguiente_asignatura = max((a.id_asignatura for a in asignaturas.values()), default=0) + 1
        for nombre in nombres:
            if nombre not in asignaturas:
                asignatura = Asignatura(id_asignatura=siguiente_asignatura, nombre_asignatura=nombre)
                asignatura.save(force_insert=True)
                asignaturas[nombre] = asignatura
                siguiente_asignatura += 1
                creadas += 1

        existentes = list(AsignaturaCurso.objects.all())
        pares = {(r.curso_id_curso_id, r.asignatura_id_asignatura_id) for r in existentes}
        siguiente_relacion = max((r.id_asig_curso for r in existentes), default=0) + 1
        for curso, materias in planes:
            for nombre in materias:
                asignatura = asignaturas[nombre]
                par = (curso.id_curso, asignatura.id_asignatura)
                if par not in pares:
                    AsignaturaCurso(
                        id_asig_curso=siguiente_relacion,
                        curso_id_curso=curso,
                        asignatura_id_asignatura=asignatura,
                        usuario_rut_id=curso.usuario_rut_id,
                    ).save(force_insert=True)
                    pares.add(par)
                    siguiente_relacion += 1
                    relaciones_creadas += 1

    print(f'Asignaturas creadas: {creadas}')
    print(f'Relaciones creadas: {relaciones_creadas}')
    print(f'Total asignaturas en BD: {Asignatura.objects.count()}')
    print(f'Total relaciones en BD: {AsignaturaCurso.objects.count()}')
    print('Alumnos, apoderados y calificaciones: sin cambios.')

if __name__ == '__main__':
    main()
