from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from sistema.models import EquipoTi
from .auth_views import require_role


@require_role([1, 4])
def inventario_ti(request):
    query = request.GET.get('q', '').strip()
    
    equipos_qs = EquipoTi.objects.all().order_by('codigo_inventario')

    if query:
        palabras = query.split()
        for palabra in palabras:
            equipos_qs = equipos_qs.filter(
                Q(codigo_inventario__icontains=palabra) |
                Q(ubicacion__icontains=palabra) |
                Q(tipo_equipo__icontains=palabra) |
                Q(estado__icontains=palabra)
            )

    todos_equipos = EquipoTi.objects.all()
    total_equipos = todos_equipos.count()
    operativos = todos_equipos.filter(estado__iexact='Disponible').count()
    en_mantencion = todos_equipos.filter(estado__iexact='En Mantención').count()

    paginator = Paginator(equipos_qs, 10)
    page_number = request.GET.get('page')
    equipos_paginados = paginator.get_page(page_number)

    return render(request, 'inventario_ti.html', {
        'equipos': equipos_paginados,
        'query': query,
        'total_equipos': total_equipos,
        'operativos': operativos,
        'en_mantencion': en_mantencion,
    })


@require_role([1, 4])
def admin_editar_equipo(request, codigo):
    equipo = get_object_or_404(EquipoTi, codigo_inventario=codigo)

    if request.method == 'POST':
        equipo.codigo_inventario = request.POST.get('codigo_inventario', '').strip()
        equipo.tipo_equipo = request.POST.get('tipo_equipo', '').strip()
        equipo.ubicacion = request.POST.get('ubicacion', '').strip()
        equipo.estado = request.POST.get('estado', 'Disponible')

        equipo.save()
        messages.success(request, f"Equipo {equipo.codigo_inventario} actualizado correctamente.")
        return redirect('inventario_ti')

    return render(request, 'admin_editar_equipo.html', {
        'equipo': equipo
    })


@require_role([1, 4])
def crear_equipo_ti(request):
    if request.method == 'POST':
        codigo_inventario = request.POST.get('codigo_inventario')
        tipo_equipo = request.POST.get('tipo_equipo')
        ubicacion = request.POST.get('ubicacion')
        estado = request.POST.get('estado', 'Disponible')

        EquipoTi.objects.create(
            codigo_inventario=codigo_inventario,
            tipo_equipo=tipo_equipo,
            ubicacion=ubicacion,
            estado=estado
        )
        messages.success(request, 'Equipo tecnológico registrado exitosamente.')
        return redirect('inventario_ti')

    return render(request, 'crear_equipo_ti.html')