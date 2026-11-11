from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError
from sistema.models import EquipoTi
from .auth_views import require_role


@require_role([1, 4])
def inventario_ti(request):
    estado_filtro = request.GET.get('estado', 'Todos')
    busqueda = request.GET.get('q', '').strip()
    
    equipos_list = EquipoTi.objects.all().order_by('-codigo_inventario')
    
    # Filtro por estado
    if estado_filtro and estado_filtro != 'Todos':
        equipos_list = equipos_list.filter(estado=estado_filtro)
        
    # Buscador por texto (Código, Tipo o Ubicación)
    if busqueda:
        equipos_list = equipos_list.filter(
            Q(codigo_inventario__icontains=busqueda) |
            Q(tipo_equipo__icontains=busqueda) |
            Q(ubicacion__icontains=busqueda)
        )

    # Paginación (ej. 10 por página)
    paginator = Paginator(equipos_list, 10)
    page_number = request.GET.get('page')
    equipos = paginator.get_page(page_number)

    # Métricas del dashboard superior
    total_equipos = EquipoTi.objects.count()
    disponibles = EquipoTi.objects.filter(estado='Disponible').count()
    operativos = EquipoTi.objects.filter(estado='Operativo').count()
    en_mantencion = EquipoTi.objects.filter(estado='En Mantención').count()

    context = {
        'equipos': equipos,
        'estado_filtro': estado_filtro,
        'busqueda': busqueda,
        'total_equipos': total_equipos,
        'disponibles': disponibles,
        'operativos': operativos,
        'en_mantencion': en_mantencion,
    }
    return render(request, 'ti/inventario_ti.html', context)


@require_role([1, 4])
def admin_editar_equipo(request, codigo):
    equipo = get_object_or_404(EquipoTi, codigo_inventario=codigo)

    if request.method == 'POST':
        equipo.codigo_inventario = request.POST.get('codigo_inventario', '').strip()
        equipo.tipo_equipo = request.POST.get('tipo_equipo', '').strip() # <--- Esto actualiza el tipo
        equipo.ubicacion = request.POST.get('ubicacion', '').strip()
        equipo.estado = request.POST.get('estado', 'Disponible')

        equipo.save()
        messages.success(request, f"Equipo {equipo.codigo_inventario} actualizado correctamente.")
        return redirect('inventario_ti')

    return render(request, 'admin/admin_editar_equipo.html', {
        'equipo': equipo
    })


@require_role([1, 4])
def admin_eliminar_equipo(request, codigo):
    equipo = get_object_or_404(EquipoTi, codigo_inventario=codigo)
    try:
        equipo.delete()
        messages.success(request, f"Equipo {codigo} eliminado correctamente del inventario.")
    except IntegrityError:
        messages.error(request, f"No se puede eliminar el equipo '{codigo}' porque tiene tickets o incidencias de soporte asociadas.")
    
    return redirect('inventario_ti')


@require_role([1, 4])
def crear_equipo_ti(request):
    if request.method == 'POST':
        codigo_inventario = request.POST.get('codigo_inventario', '').strip()
        tipo_equipo = request.POST.get('tipo_equipo', '').strip()
        ubicacion = request.POST.get('ubicacion', '').strip()
        estado = request.POST.get('estado', 'Disponible')
        
        # Capturamos la cantidad (si no viene o está vacía, por defecto es 1)
        try:
            cantidad = int(request.POST.get('cantidad', 1))
        except ValueError:
            cantidad = 1

        # Si la cantidad es mayor a 1, generamos un lote masivo correlativo
        if cantidad > 1:
            creados = 0
            duplicados = []
            
            for i in range(1, cantidad + 1):
                codigo_actual = f"{codigo_inventario}-{i:03d}"
                
                if EquipoTi.objects.filter(codigo_inventario=codigo_actual).exists():
                    duplicados.append(codigo_actual)
                    continue
                
                EquipoTi.objects.create(
                    codigo_inventario=codigo_actual,
                    tipo_equipo=tipo_equipo,
                    ubicacion=ubicacion,
                    estado=estado
                )
                creados += 1
            
            if creados > 0:
                messages.success(request, f"¡Lote generado con éxito! Se registraron {creados} equipos nuevos.")
            if duplicados:
                messages.warning(request, f"Se omitieron {len(duplicados)} códigos porque ya existían en el sistema.")
            
            return redirect('inventario_ti')

        # Registro individual clásico (cuando la cantidad es 1)
        if EquipoTi.objects.filter(codigo_inventario=codigo_inventario).exists():
            messages.error(request, f"El código de inventario '{codigo_inventario}' ya se encuentra registrado.")
            return render(request, 'ti/crear_equipo_ti.html')

        EquipoTi.objects.create(
            codigo_inventario=codigo_inventario,
            tipo_equipo=tipo_equipo,
            ubicacion=ubicacion,
            estado=estado
        )
        messages.success(request, 'Equipo tecnológico registrado exitosamente.')
        return redirect('inventario_ti')

    return render(request, 'ti/crear_equipo_ti.html')