from collections import defaultdict
from io import BytesIO
from html import escape

from django.http import Http404, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A3, landscape
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    LongTable,
    TableStyle,
    KeepTogether
)

from sistema.models import Alumno, AsignaturaCurso, Calificacion, RegistroAsistencia
from .auth_views import require_role


@require_role([3])
def apoderado_inicio(request):
    rut_apoderado = request.session.get('usuario_rut')
    alumnos = Alumno.objects.filter(usuario_rut_id=rut_apoderado).select_related('curso_id_curso')
    
    context = {
        'alumnos': alumnos,
    }
    return render(request, 'apoderado/apoderado_inicio.html', context)


@require_role([3])
def apoderado_certificados(request):
    rut_apoderado = request.session.get('usuario_rut')

    alumnos = list(
        Alumno.objects
        .filter(usuario_rut_id=rut_apoderado)
        .select_related('curso_id_curso')
        .order_by('nombre_completo')
    )

    rut_solicitado = request.GET.get('alumno', '').strip()

    if rut_solicitado:
        alumno_seleccionado = next(
            (a for a in alumnos if a.rut_alumno == rut_solicitado),
            None
        )
        if alumno_seleccionado is None:
            raise Http404('Estudiante no asociado a este apoderado.')
    else:
        alumno_seleccionado = alumnos[0] if alumnos else None

    tipo_certificado = request.GET.get('tipo', 'regular')
    if tipo_certificado not in ('regular', 'notas'):
        tipo_certificado = 'regular'

    resumen_notas = []
    numeros_evaluacion = set()
    promedios = []

    if alumno_seleccionado and tipo_certificado == 'notas':
        asignaturas = list(
            AsignaturaCurso.objects
            .filter(curso_id_curso=alumno_seleccionado.curso_id_curso)
            .select_related('asignatura_id_asignatura')
            .order_by('asignatura_id_asignatura__nombre_asignatura')
        )

        calificaciones = (
            Calificacion.objects
            .filter(
                alumno_rut_alumno=alumno_seleccionado,
                asignatura_curso_id_asig_curso__curso_id_curso=
                    alumno_seleccionado.curso_id_curso
            )
            .select_related('evaluacion_id_evaluacion')
            .order_by('fecha_ingreso', 'id_calificacion')
        )

        por_asignatura = defaultdict(dict)

        for calificacion in calificaciones:
            evaluacion = calificacion.evaluacion_id_evaluacion

            if evaluacion is None:
                continue

            numero = evaluacion.numero_evaluacion
            asignatura_id = (
                calificacion.asignatura_curso_id_asig_curso_id
            )

            por_asignatura[asignatura_id][numero] = (
                calificacion.valor_nota
            )
            numeros_evaluacion.add(numero)

        numeros_evaluacion = sorted(numeros_evaluacion)

        for asignatura in asignaturas:
            notas = por_asignatura.get(
                asignatura.id_asig_curso, {}
            )

            valores = list(notas.values())
            promedio = (
                round(sum(valores) / len(valores), 1)
                if valores else None
            )

            if promedio is not None:
                promedios.append(
                    sum(valores) / len(valores)
                )

            resumen_notas.append({
                'nombre_asignatura':
                    asignatura.asignatura_id_asignatura.nombre_asignatura,
                'notas': [
                    {'numero': numero, 'valor': notas.get(numero)}
                    for numero in numeros_evaluacion
                ],
                'promedio': promedio
            })

    promedio_general = (
        round(sum(promedios) / len(promedios), 1)
        if promedios else None
    )

    return render(request, 'apoderado/apoderado_certificados.html', {
        'alumnos': alumnos,
        'alumno_seleccionado': alumno_seleccionado,
        'tipo_certificado': tipo_certificado,
        'resumen_notas': resumen_notas,
        'numeros_evaluacion': numeros_evaluacion,
        'promedio_general': promedio_general,
        'fecha_emision': timezone.localdate(),
        'anio_escolar': timezone.localdate().year,
    })


@require_role([3])
def apoderado_descargar_certificado(request):
    rut_apoderado = request.session.get('usuario_rut')
    rut_alumno = request.GET.get('alumno', '').strip()
    tipo = request.GET.get('tipo', 'regular').strip()

    if tipo not in ('regular', 'notas'):
        raise Http404('Tipo de certificado inválido.')

    alumno = (
        Alumno.objects
        .filter(
            rut_alumno=rut_alumno,
            usuario_rut_id=rut_apoderado
        )
        .select_related('curso_id_curso')
        .first()
    )

    if alumno is None:
        raise Http404('Estudiante no asociado a este apoderado.')

    AZUL = colors.HexColor('#17365D')
    AZUL_OSCURO = colors.HexColor('#102A47')
    AZUL_CLARO = colors.HexColor('#EAF2FB')
    NARANJA = colors.HexColor('#F97316')
    NARANJA_CLARO = colors.HexColor('#FFF3E9')
    GRIS = colors.HexColor('#64748B')
    GRIS_CLARO = colors.HexColor('#F8FAFC')
    BORDE = colors.HexColor('#DCE5EF')
    VERDE = colors.HexColor('#15803D')
    ROJO = colors.HexColor('#DC2626')

    fecha_emision = timezone.localdate()
    anio_escolar = fecha_emision.year

    nombre_alumno = escape(str(alumno.nombre_completo))
    rut_estudiante = escape(str(alumno.rut_alumno))
    nombre_curso = escape(str(alumno.curso_id_curso.nombre_curso))

    buffer = BytesIO()

    pagina = landscape(A3) if tipo == 'notas' else A4

    documento = SimpleDocTemplate(
        buffer,
        pagesize=pagina,
        leftMargin=2.1 * cm,
        rightMargin=2.1 * cm,
        topMargin=4.3 * cm,
        bottomMargin=4.0 * cm if tipo == 'regular' else 2.5 * cm,
        title=(
            'Certificado de Calificaciones'
            if tipo == 'notas'
            else 'Certificado de Alumno Regular'
        ),
        author='Sistema de Gestión Escolar - Santa Juliana'
    )

    ancho_pagina, alto_pagina = pagina
    ancho_util = (
        ancho_pagina
        - documento.leftMargin
        - documento.rightMargin
    )

    estilos = getSampleStyleSheet()

    estilos.add(ParagraphStyle(
        name='TituloSGE',
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=23,
        textColor=AZUL_OSCURO,
        alignment=TA_CENTER,
        spaceAfter=9
    ))

    estilos.add(ParagraphStyle(
        name='SubtituloSGE',
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=GRIS,
        alignment=TA_CENTER,
        spaceAfter=12
    ))

    estilos.add(ParagraphStyle(
        name='TextoSGE',
        fontName='Helvetica',
        fontSize=10.5,
        leading=18,
        textColor=AZUL_OSCURO,
        alignment=TA_LEFT,
        spaceAfter=14
    ))

    estilos.add(ParagraphStyle(
        name='EtiquetaSGE',
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=14,
        textColor=AZUL
    ))

    estilos.add(ParagraphStyle(
        name='ValorSGE',
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        textColor=AZUL_OSCURO
    ))

    estilos.add(ParagraphStyle(
        name='SeccionSGE',
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=16,
        textColor=AZUL,
        spaceBefore=8,
        spaceAfter=12
    ))

    estilos.add(ParagraphStyle(
        name='CeldaSGE',
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=AZUL_OSCURO
    ))

    estilos.add(ParagraphStyle(
        name='CeldaNegritaSGE',
        parent=estilos['CeldaSGE'],
        fontName='Helvetica-Bold'
    ))

    estilos.add(ParagraphStyle(
        name='CeldaBlancaSGE',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white
    ))

    estilos.add(ParagraphStyle(
        name='NotaSGE',
        fontName='Helvetica',
        fontSize=8.5,
        leading=13,
        textColor=GRIS,
        spaceAfter=8
    ))

    def decorar_pagina(canvas, doc):
        canvas.saveState()

        canvas.setFillColor(AZUL)
        canvas.rect(
            0,
            alto_pagina - 2.75 * cm,
            ancho_pagina,
            2.75 * cm,
            fill=1,
            stroke=0
        )

        canvas.setFillColor(NARANJA)
        canvas.rect(
            0,
            alto_pagina - 2.86 * cm,
            ancho_pagina,
            0.11 * cm,
            fill=1,
            stroke=0
        )

        canvas.setFillColor(NARANJA)
        canvas.roundRect(
            2.0 * cm,
            alto_pagina - 2.05 * cm,
            1.25 * cm,
            1.05 * cm,
            7,
            fill=1,
            stroke=0
        )

        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawCentredString(
            2.625 * cm,
            alto_pagina - 1.67 * cm,
            'SGE'
        )

        canvas.setFillColor(colors.white)
        canvas.setFont('Helvetica-Bold', 13)
        canvas.drawString(
            3.6 * cm,
            alto_pagina - 1.36 * cm,
            'LICEO POLIVALENTE SANTA JULIANA'
        )

        canvas.setFont('Helvetica', 9)
        canvas.drawString(
            3.6 * cm,
            alto_pagina - 1.81 * cm,
            'Sistema de Gestión Escolar'
        )

        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawRightString(
            ancho_pagina - 2.0 * cm,
            alto_pagina - 1.48 * cm,
            f'AÑO ESCOLAR {anio_escolar}'
        )

        canvas.saveState()
        canvas.setFillColor(colors.HexColor('#F1F5F9'))
        canvas.setFont('Helvetica-Bold', 70)
        canvas.translate(
            ancho_pagina / 2,
            alto_pagina / 2
        )
        canvas.rotate(35)
        canvas.drawCentredString(0, 0, 'SGE')
        canvas.restoreState()

        canvas.setStrokeColor(BORDE)
        canvas.setLineWidth(0.7)
        canvas.line(
            2 * cm,
            1.65 * cm,
            ancho_pagina - 2 * cm,
            1.65 * cm
        )

        canvas.setFillColor(AZUL)
        canvas.setFont('Helvetica-Bold', 8)
        canvas.drawString(
            2 * cm,
            1.30 * cm,
            'LICEO POLIVALENTE SANTA JULIANA'
        )

        canvas.setFillColor(GRIS)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawString(
            2 * cm,
            1.02 * cm,
            'Documento generado por el Sistema de Gestión Escolar'
        )

        canvas.drawRightString(
            ancho_pagina - 2 * cm,
            1.30 * cm,
            f'Emitido: {fecha_emision.strftime("%d/%m/%Y")}'
        )

        canvas.drawRightString(
            ancho_pagina - 2 * cm,
            1.02 * cm,
            f'Página {doc.page}'
        )

        if tipo == 'regular' and doc.page == 1:
            firma_x = ancho_pagina - 7.1 * cm
            firma_y = 5.1 * cm

            canvas.setStrokeColor(AZUL)
            canvas.setLineWidth(1.5)

            trazo = canvas.beginPath()
            trazo.moveTo(firma_x + 0.1 * cm, firma_y)
            trazo.curveTo(
                firma_x + 0.7 * cm, firma_y + 0.8 * cm,
                firma_x + 0.6 * cm, firma_y - 0.4 * cm,
                firma_x + 1.7 * cm, firma_y + 0.5 * cm
            )
            trazo.curveTo(
                firma_x + 2.2 * cm, firma_y + 0.9 * cm,
                firma_x + 1.6 * cm, firma_y - 0.2 * cm,
                firma_x + 3.0 * cm, firma_y + 0.35 * cm
            )
            trazo.curveTo(
                firma_x + 3.5 * cm, firma_y + 0.7 * cm,
                firma_x + 3.7 * cm, firma_y - 0.2 * cm,
                firma_x + 4.4 * cm, firma_y + 0.2 * cm
            )
            canvas.drawPath(trazo)

            canvas.setStrokeColor(GRIS)
            canvas.setLineWidth(0.6)
            canvas.line(
                firma_x - 0.2 * cm,
                firma_y - 0.45 * cm,
                firma_x + 5 * cm,
                firma_y - 0.45 * cm
            )

            canvas.setFillColor(AZUL_OSCURO)
            canvas.setFont('Helvetica-Bold', 9)
            canvas.drawCentredString(
                firma_x + 2.4 * cm,
                firma_y - 0.85 * cm,
                'Dirección del Establecimiento'
            )

            canvas.setFillColor(GRIS)
            canvas.setFont('Helvetica', 7.5)
            canvas.drawCentredString(
                firma_x + 2.4 * cm,
                firma_y - 1.15 * cm,
                'Firma ilustrativa - No autorizada'
            )

        canvas.restoreState()

    contenido = []

    titulo = (
        'CERTIFICADO DE CALIFICACIONES'
        if tipo == 'notas'
        else 'CERTIFICADO DE ALUMNO REGULAR'
    )

    contenido.append(Paragraph(titulo, estilos['TituloSGE']))
    contenido.append(Paragraph(f'Período académico {anio_escolar}', estilos['SubtituloSGE']))
    contenido.append(Spacer(1, 0.35 * cm))
    contenido.append(Paragraph('ANTECEDENTES DEL ESTUDIANTE', estilos['SeccionSGE']))

    datos = [
        [
            Paragraph('Nombre completo:', estilos['EtiquetaSGE']),
            Paragraph(nombre_alumno, estilos['ValorSGE'])
        ],
        [
            Paragraph('R.U.T:', estilos['EtiquetaSGE']),
            Paragraph(rut_estudiante, estilos['ValorSGE'])
        ],
        [
            Paragraph('Curso:', estilos['EtiquetaSGE']),
            Paragraph(nombre_curso, estilos['ValorSGE'])
        ],
        [
            Paragraph('Año escolar:', estilos['EtiquetaSGE']),
            Paragraph(str(anio_escolar), estilos['ValorSGE'])
        ]
    ]

    tabla_datos = Table(
        datos,
        colWidths=[ancho_util * 0.30, ancho_util * 0.70],
        hAlign='LEFT'
    )

    tabla_datos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), GRIS_CLARO),
        ('BACKGROUND', (0, 0), (0, -1), AZUL_CLARO),
        ('LINEBELOW', (0, 0), (-1, -2), 0.4, BORDE),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDE),
        ('LEFTPADDING', (0, 0), (-1, -1), 13),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')
    ]))

    contenido.append(tabla_datos)
    contenido.append(Spacer(1, 0.75 * cm))

    if tipo == 'regular':
        contenido.append(Paragraph('CERTIFICACIÓN DE MATRÍCULA', estilos['SeccionSGE']))
        contenido.append(
            Paragraph(
                'La Dirección del '
                '<b>Liceo Polivalente Santa Juliana</b> '
                'deja constancia de que el estudiante '
                f'<b>{nombre_alumno}</b>, '
                f'R.U.T. <b>{rut_estudiante}</b>, '
                'se encuentra registrado en el '
                'establecimiento educacional, '
                f'en el curso <b>{nombre_curso}</b>, '
                f'correspondiente al año escolar '
                f'<b>{anio_escolar}</b>.',
                estilos['TextoSGE']
            )
        )

        contenido.append(
            Paragraph(
                'El presente documento se emite '
                'a solicitud del apoderado para '
                'los fines que estime pertinentes.',
                estilos['TextoSGE']
            )
        )

        contenido.append(Spacer(1, 0.35 * cm))

        recuadro = Table(
            [[Paragraph(
                '<b>INFORMACIÓN IMPORTANTE</b><br/>'
                'Este certificado ha sido generado '
                'por el Sistema de Gestión Escolar. '
                'Su validez oficial requiere '
                'la autorización del establecimiento.',
                estilos['NotaSGE']
            )]],
            colWidths=[ancho_util]
        )

        recuadro.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), NARANJA_CLARO),
            ('LINEBEFORE', (0, 0), (0, 0), 3, NARANJA),
            ('LEFTPADDING', (0, 0), (-1, -1), 14),
            ('RIGHTPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8)
        ]))

        contenido.append(recuadro)
        contenido.append(Spacer(1, 0.45 * cm))
        contenido.append(Paragraph(f'Santiago, Chile - {fecha_emision.strftime("%d/%m/%Y")}', estilos['TextoSGE']))

    else:
        contenido.append(Paragraph('DETALLE DE CALIFICACIONES REGISTRADAS', estilos['SeccionSGE']))

        asignaturas = list(
            AsignaturaCurso.objects
            .filter(curso_id_curso=alumno.curso_id_curso)
            .select_related('asignatura_id_asignatura')
            .order_by('asignatura_id_asignatura__nombre_asignatura')
        )

        calificaciones = (
            Calificacion.objects
            .filter(
                alumno_rut_alumno=alumno,
                asignatura_curso_id_asig_curso__curso_id_curso=alumno.curso_id_curso
            )
            .select_related('evaluacion_id_evaluacion')
            .order_by('fecha_ingreso', 'id_calificacion')
        )

        notas_por_asignatura = defaultdict(dict)
        numeros = set()

        for calificacion in calificaciones:
            evaluacion = calificacion.evaluacion_id_evaluacion

            if evaluacion is None or calificacion.valor_nota is None:
                continue

            numero = evaluacion.numero_evaluacion
            asignatura_id = calificacion.asignatura_curso_id_asig_curso_id

            notas_por_asignatura[asignatura_id][numero] = float(calificacion.valor_nota)
            numeros.add(numero)

        numeros = sorted(numeros)

        cabecera = [Paragraph('ASIGNATURA', estilos['CeldaBlancaSGE'])]
        for numero in numeros:
            cabecera.append(Paragraph(f'NOTA {numero}', estilos['CeldaBlancaSGE']))
        cabecera.append(Paragraph('PROMEDIO', estilos['CeldaBlancaSGE']))

        filas = [cabecera]
        promedios = []

        for asignatura in asignaturas:
            notas = notas_por_asignatura.get(asignatura.id_asig_curso, {})
            valores = list(notas.values())

            promedio = sum(valores) / len(valores) if valores else None
            if promedio is not None:
                promedios.append(promedio)

            nombre = escape(str(asignatura.asignatura_id_asignatura.nombre_asignatura))
            fila = [Paragraph(nombre, estilos['CeldaSGE'])]

            for numero in numeros:
                valor = notas.get(numero)
                fila.append(f'{valor:.1f}' if valor is not None else '-')

            fila.append(f'{promedio:.1f}' if promedio is not None else '-')
            filas.append(fila)

        promedio_general = sum(promedios) / len(promedios) if promedios else None

        filas.append(
            [Paragraph('PROMEDIO GENERAL', estilos['CeldaNegritaSGE'])]
            + [''] * len(numeros)
            + [f'{promedio_general:.1f}' if promedio_general is not None else '-']
        )

        ancho_asignatura = min(8.5 * cm, ancho_util * 0.30)
        cantidad_columnas = len(numeros) + 1
        ancho_nota = (ancho_util - ancho_asignatura) / cantidad_columnas

        tabla_notas = LongTable(
            filas,
            colWidths=[ancho_asignatura] + [ancho_nota] * cantidad_columnas,
            repeatRows=1,
            hAlign='LEFT'
        )

        tamano_fuente = 8 if len(numeros) <= 12 else (6 if len(numeros) <= 22 else 4.5)

        tabla_notas.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), AZUL),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, GRIS_CLARO]),
            ('BACKGROUND', (0, -1), (-1, -1), AZUL_CLARO),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.35, BORDE),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), tamano_fuente),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, NARANJA)
        ]))

        for indice_fila, asignatura in enumerate(asignaturas, start=1):
            notas = notas_por_asignatura.get(asignatura.id_asig_curso, {})

            for indice_columna, numero in enumerate(numeros, start=1):
                valor = notas.get(numero)
                if valor is not None:
                    tabla_notas.setStyle(TableStyle([
                        ('TEXTCOLOR', (indice_columna, indice_fila), (indice_columna, indice_fila), ROJO if valor < 4 else AZUL)
                    ]))

            valores = list(notas.values())
            if valores:
                promedio = sum(valores) / len(valores)
                tabla_notas.setStyle(TableStyle([
                    ('TEXTCOLOR', (-1, indice_fila), (-1, indice_fila), ROJO if promedio < 4 else VERDE),
                    ('FONTNAME', (-1, indice_fila), (-1, indice_fila), 'Helvetica-Bold')
                ]))

        if promedio_general is not None:
            tabla_notas.setStyle(TableStyle([
                ('TEXTCOLOR', (-1, -1), (-1, -1), ROJO if promedio_general < 4 else VERDE)
            ]))

        contenido.append(tabla_notas)
        contenido.append(Spacer(1, 0.65 * cm))

        total_asignaturas = len(asignaturas)
        asignaturas_con_notas = len(promedios)

        resumen = [
            [
                Paragraph('<b>ASIGNATURAS</b>', estilos['EtiquetaSGE']),
                Paragraph('<b>CON CALIFICACIONES</b>', estilos['EtiquetaSGE']),
                Paragraph('<b>PROMEDIO GENERAL</b>', estilos['EtiquetaSGE'])
            ],
            [
                str(total_asignaturas),
                str(asignaturas_con_notas),
                f'{promedio_general:.1f}' if promedio_general is not None else '-'
            ]
        ]

        tabla_resumen = Table(resumen, colWidths=[ancho_util / 3] * 3)

        tabla_resumen.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), AZUL_CLARO),
            ('BOX', (0, 0), (-1, -1), 0.7, BORDE),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, BORDE),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 17),
            ('TEXTCOLOR', (0, 1), (-1, 1), AZUL),
            ('TOPPADDING', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 11)
        ]))

        contenido.append(KeepTogether([
            tabla_resumen,
            Spacer(1, 0.45 * cm),
            Paragraph(
                'El promedio general corresponde al promedio '
                'de las asignaturas que tienen calificaciones '
                'registradas. Las asignaturas sin notas no '
                'participan en este cálculo.',
                estilos['NotaSGE']
            ),
            Paragraph(
                'Las calificaciones reflejan los registros '
                'disponibles en el sistema al momento '
                'de generar el certificado.',
                estilos['NotaSGE']
            )
        ]))

        contenido.append(Spacer(1, 0.25 * cm))
        contenido.append(
            Paragraph(
                'Documento informativo generado por SGE. '
                'Su validez oficial requiere autorización '
                'del establecimiento.',
                estilos['NotaSGE']
            )
        )

    documento.build(
        contenido,
        onFirstPage=decorar_pagina,
        onLaterPages=decorar_pagina
    )

    pdf = buffer.getvalue()
    buffer.close()

    nombre_archivo = (
        f'certificado_{tipo}_{alumno.rut_alumno}.pdf'
    )

    respuesta = HttpResponse(
        pdf,
        content_type='application/pdf'
    )

    respuesta['Content-Disposition'] = (
        f'attachment; filename="{nombre_archivo}"'
    )

    return respuesta

@require_role([3])
def apoderado_notas(request):
    from django.http import Http404
    from sistema.models import Alumno, AsignaturaCurso, Calificacion

    rut_apoderado = request.session.get('usuario_rut')

    alumnos = list(
        Alumno.objects
        .filter(usuario_rut_id=rut_apoderado)
        .select_related('curso_id_curso')
        .order_by('nombre_completo')
    )

    rut_solicitado = request.GET.get('alumno', '').strip()

    if rut_solicitado:
        alumno_seleccionado = next(
            (a for a in alumnos if a.rut_alumno == rut_solicitado),
            None
        )

        if alumno_seleccionado is None:
            raise Http404(
                'Estudiante no asociado a este apoderado.'
            )
    else:
        alumno_seleccionado = alumnos[0] if alumnos else None

    resumen_notas = []
    numeros_evaluacion = set()

    if alumno_seleccionado:

        asignaturas = list(
            AsignaturaCurso.objects
            .filter(
                curso_id_curso=alumno_seleccionado.curso_id_curso
            )
            .select_related('asignatura_id_asignatura')
            .order_by(
                'asignatura_id_asignatura__nombre_asignatura'
            )
        )

        calificaciones = (
            Calificacion.objects
            .filter(
                alumno_rut_alumno=alumno_seleccionado,
                asignatura_curso_id_asig_curso__curso_id_curso=
                    alumno_seleccionado.curso_id_curso
            )
            .select_related('evaluacion_id_evaluacion')
            .order_by('fecha_ingreso', 'id_calificacion')
        )

        notas_por_asignatura = {}

        for calificacion in calificaciones:

            id_asignatura = (
                calificacion.asignatura_curso_id_asig_curso_id
            )

            evaluacion = calificacion.evaluacion_id_evaluacion

            if evaluacion is None:
                continue

            numero = evaluacion.numero_evaluacion

            numeros_evaluacion.add(numero)

            if id_asignatura not in notas_por_asignatura:
                notas_por_asignatura[id_asignatura] = {}

            # Si hay registros repetidos de una misma evaluación,
            # se muestra el último según el orden de consulta.
            notas_por_asignatura[id_asignatura][numero] = calificacion

        # Se muestran al menos tres columnas.
        total_columnas = max(
            max(numeros_evaluacion, default=0),
            3
        )

        columnas_notas = list(range(1, total_columnas + 1))

        for asignatura_curso in asignaturas:

            notas_registradas = notas_por_asignatura.get(
                asignatura_curso.id_asig_curso,
                {}
            )

            notas_ordenadas = []

            for numero in columnas_notas:

                calificacion = notas_registradas.get(numero)

                notas_ordenadas.append({
                    'numero': numero,
                    'calificacion': calificacion,
                })

            valores = [
                nota.valor_nota
                for nota in notas_registradas.values()
                if nota.valor_nota is not None
            ]

            promedio = (
                round(sum(valores) / len(valores), 1)
                if valores else None
            )

            resumen_notas.append({
                'nombre_asignatura':
                    asignatura_curso.asignatura_id_asignatura.nombre_asignatura,
                'notas_ordenadas': notas_ordenadas,
                'promedio': promedio,
            })

    else:
        columnas_notas = [1, 2, 3]

    return render(request, 'apoderado/apoderado_notas.html', {
        'alumnos': alumnos,
        'alumno_seleccionado': alumno_seleccionado,
        'resumen_notas': resumen_notas,
        'columnas_notas': columnas_notas,
        'total_columnas_tabla': len(columnas_notas) + 2,
    })

@require_role([3])
def apoderado_asistencia(request):
    import calendar
    from datetime import date
    from django.http import Http404
    from django.utils import timezone

    rut_apoderado = request.session.get('usuario_rut')

    alumnos = list(
        Alumno.objects
        .filter(usuario_rut_id=rut_apoderado)
        .select_related('curso_id_curso')
        .order_by('nombre_completo')
    )

    rut_solicitado = request.GET.get('alumno', '').strip()

    if rut_solicitado:
        alumno_seleccionado = next(
            (alumno for alumno in alumnos
             if alumno.rut_alumno == rut_solicitado),
            None
        )

        if alumno_seleccionado is None:
            raise Http404(
                'Estudiante no asociado a este apoderado.'
            )
    else:
        alumno_seleccionado = alumnos[0] if alumnos else None

    hoy = timezone.localdate()

    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))

        if not (1 <= anio <= 9999 and 1 <= mes <= 12):
            raise ValueError

    except (ValueError, TypeError):
        anio = hoy.year
        mes = hoy.month

    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(
        anio, mes, calendar.monthrange(anio, mes)[1]
    )

    if mes == 1:
        mes_anterior = 12
        anio_anterior = anio - 1
    else:
        mes_anterior = mes - 1
        anio_anterior = anio

    if mes == 12:
        mes_siguiente = 1
        anio_siguiente = anio + 1
    else:
        mes_siguiente = mes + 1
        anio_siguiente = anio

    nombres_meses = [
        '', 'Enero', 'Febrero', 'Marzo', 'Abril',
        'Mayo', 'Junio', 'Julio', 'Agosto',
        'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]

    estados_por_fecha = {}

    if alumno_seleccionado:
        registros = (
            RegistroAsistencia.objects
            .filter(
                alumno_rut_alumno=alumno_seleccionado,
                fecha__range=(primer_dia, ultimo_dia)
            )
            .order_by('-id_asistencia')
        )

        for registro in registros:
            if registro.fecha not in estados_por_fecha:
                estados_por_fecha[registro.fecha] = registro.presente

    dias_asistidos = sum(
        1 for estado in estados_por_fecha.values()
        if estado == 1
    )

    inasistencias = sum(
        1 for estado in estados_por_fecha.values()
        if estado == 0
    )

    total_registrados = dias_asistidos + inasistencias

    porcentaje_asistencia = (
        round(dias_asistidos * 100 / total_registrados, 1)
        if total_registrados else None
    )

    semanas = []
    cal = calendar.Calendar(firstweekday=0)

    for semana in cal.monthdatescalendar(anio, mes):
        dias_semana = []

        for fecha_dia in semana[:5]:

            if fecha_dia.month != mes:
                dias_semana.append({
                    'numero': None,
                    'estado': 'vacio',
                    'texto': ''
                })
                continue

            estado = estados_por_fecha.get(fecha_dia)

            if estado == 1:
                clase = 'presente'
                texto = 'ASISTIÓ'
            elif estado == 0:
                clase = 'ausente'
                texto = 'FALTÓ'
            else:
                clase = 'sin-registro'
                texto = 'SIN REGISTRO'

            dias_semana.append({
                'numero': fecha_dia.day,
                'estado': clase,
                'texto': texto,
                'fecha': fecha_dia
            })

        semanas.append(dias_semana)

    return render(request, 'apoderado/apoderado_asistencia.html', {
        'alumnos': alumnos,
        'alumno_seleccionado': alumno_seleccionado,
        'nombre_mes': nombres_meses[mes],
        'anio': anio,
        'mes': mes,
        'anio_anterior': anio_anterior,
        'mes_anterior': mes_anterior,
        'anio_siguiente': anio_siguiente,
        'mes_siguiente': mes_siguiente,
        'semanas': semanas,
        'dias_asistidos': dias_asistidos,
        'inasistencias': inasistencias,
        'total_registrados': total_registrados,
        'porcentaje_asistencia': porcentaje_asistencia,
    })