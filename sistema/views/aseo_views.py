from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Max

from sistema.models import SolicitudInsumo, Insumo, Usuario
from .auth_views import require_role


@require_role([1, 5]) 
def incidencias_personal_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    solicitudes = SolicitudInsumo.objects.all().order_by('-id_solicitud')
    return render(request, 'incidencias_personal_aseo.html', {'solicitudes': solicitudes})


def inventario_personal_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    items = Insumo.objects.all()
    return render(request, 'inventario_personal_aseo.html', {'items': items})


def retirar_stock_aseo(request, id_insumo):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    insumo = get_object_or_404(Insumo, pk=id_insumo)
    
    if request.method == 'POST':
        try:
            cantidad = int(request.POST.get('cantidad', 0))
        except ValueError:
            cantidad = 0
            
        if cantidad <= 0:
            messages.error(request, 'Debes ingresar una cantidad mayor a 0.')
        elif cantidad > insumo.stock_actual:
            messages.error(request, f'No puedes retirar {cantidad} unidades. Solo hay {insumo.stock_actual} disponibles.')
        else:
            insumo.stock_actual -= cantidad
            insumo.save()
            messages.success(request, f'Retiraste {cantidad} unidades de "{insumo.nombre_item}".')
            return redirect('inventario_aseo')
            
    return render(request, 'retirar_stock_aseo.html', {'insumo': insumo})


@require_role([1, 5])
def inicio_supervisor_aseo(request):
    total_articulos = Insumo.objects.count()
    stock_critico = Insumo.objects.filter(stock_actual__lte=5).count()
    
    ruts_aseo = Usuario.objects.filter(rol_id_rol=5).values_list('rut', flat=True)
    
    solicitudes_pendientes = SolicitudInsumo.objects.filter(
        usuario_rut__in=ruts_aseo,
        estado_solicitud='Pendiente'
    ).count()

    context = {
        'total_articulos': total_articulos,
        'stock_critico': stock_critico,
        'solicitudes_pendientes': solicitudes_pendientes,
    }
    return render(request, 'inicio_supervisor_aseo.html', context)


@require_role([1, 4, 5])
def incidencias_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    rol_id = request.session.get('rol_id')
    rut_usuario = request.session.get('usuario_rut')

    # Si es Administrador (1 o 4) ve todas; si es Personal de Aseo (5), solo las suyas
    if rol_id in [1, 4]:
        lista_solicitudes = SolicitudInsumo.objects.all().order_by('-id_solicitud')
    else:
        lista_solicitudes = SolicitudInsumo.objects.filter(usuario_rut_id=rut_usuario).order_by('-id_solicitud')
    
    paginator = Paginator(lista_solicitudes, 10)
    page_number = request.GET.get('page')
    solicitudes = paginator.get_page(page_number)
    
    context = {
        'solicitudes': solicitudes,
        'rol_id': rol_id
    }
    return render(request, 'incidencias_aseo.html', context)


def inventario_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    lista_items = Insumo.objects.all().order_by('id_insumo')
    
    paginator = Paginator(lista_items, 10)
    page_number = request.GET.get('page')
    items = paginator.get_page(page_number)
    
    context = {
        'items': items,
        'rol_id': request.session.get('rol_id')
    }
    return render(request, 'inventario_aseo.html', context)


@require_role([1, 5])
def crear_insumo_aseo(request):
    if request.method == 'POST':
        nombre_item = request.POST.get('nombre_item')
        stock_actual = request.POST.get('stock_actual', 0)
        
        ultimo_id = Insumo.objects.aggregate(max_id=Max('id_insumo'))['max_id'] or 0
        nuevo_id = ultimo_id + 1

        Insumo.objects.create(
            id_insumo=nuevo_id,
            nombre_item=nombre_item,
            stock_actual=stock_actual
        )
        messages.success(request, 'Insumo de aseo registrado exitosamente.')
        return redirect('inventario_aseo')
        
    return render(request, 'crear_insumo_aseo.html')


@require_role([1, 5])
def crear_incidencia_aseo(request):
    if 'usuario_rut' not in request.session:
        return redirect('login')

    if request.method == 'POST':
        tipo_solicitud = request.POST.get('tipo_incidencia')
        descripcion = request.POST.get('descripcion')
        fecha_incidencia = request.POST.get('fecha_incidencia') or date.today()
        rut_sesion = request.session.get('usuario_rut')

        try:
            usuario_obj = get_object_or_404(Usuario, pk=rut_sesion)

            max_id = SolicitudInsumo.objects.aggregate(Max('id_solicitud'))['id_solicitud__max']
            nuevo_id = (max_id or 0) + 1

            SolicitudInsumo.objects.create(
                id_solicitud=nuevo_id,
                fecha=fecha_incidencia,
                tipo_solicitud=tipo_solicitud,
                descripcion=descripcion,
                estado_solicitud='Pendiente',
                usuario_rut=usuario_obj
            )

            messages.success(request, '¡Solicitud de aseo registrada con éxito!')
            return redirect('incidencias_aseo')

        except Exception as e:
            messages.error(request, f'Ocurrió un error al guardar la solicitud: {str(e)}')
            return render(request, 'crear_incidencia_aseo.html')

    return render(request, 'crear_incidencia_aseo.html')


@require_role([1, 5])
def resolver_solicitud_aseo(request, id_solicitud):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    solicitud = get_object_or_404(SolicitudInsumo, id_solicitud=id_solicitud)
    
    if request.method == 'POST':
        try:
            nuevo_estado = request.POST.get('estado_solicitud', 'Resuelto')
            observaciones = request.POST.get('observaciones', '')
            
            solicitud.estado_solicitud = nuevo_estado
            solicitud.observaciones = observaciones
            solicitud.save()
            
            messages.success(request, f'¡Solicitud #{id_solicitud} actualizada correctamente!')
            return redirect('incidencias_aseo')

        except Exception as e:
            messages.error(request, f'Error al actualizar la solicitud: {str(e)}')
        
    context = {
        'solicitud': solicitud
    }
    return render(request, 'resolver_solicitud_aseo.html', context)


@require_role([1, 5])
def ajustar_stock_insumo(request, id_insumo):
    if 'usuario_rut' not in request.session:
        return redirect('login')
        
    insumo = get_object_or_404(Insumo, pk=id_insumo)
    
    if request.method == 'POST':
        accion = request.POST.get('accion')
        
        try:
            cantidad = int(request.POST.get('cantidad', 0))
            if cantidad < 0:
                messages.warning(request, 'La cantidad debe ser un número positivo.')
                return render(request, 'ajustar_stock_insumo.html', {'insumo': insumo})
                
            if accion == 'sumar':
                insumo.stock_actual += cantidad
            elif accion == 'restar':
                insumo.stock_actual = max(0, insumo.stock_actual - cantidad)
            elif accion == 'fijar':
                insumo.stock_actual = max(0, cantidad)
                
            insumo.save()
            messages.success(request, f'¡Stock de "{insumo.nombre_item}" actualizado con éxito!')
            return redirect('inventario_aseo')

        except ValueError:
            messages.error(request, 'Por favor ingrese una cantidad numérica válida.')
        except Exception as e:
            messages.error(request, f'Error al guardar en base de datos: {str(e)}')
        
    context = {
        'insumo': insumo
    }
    return render(request, 'ajustar_stock_insumo.html', context)