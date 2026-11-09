from datetime import datetime
from functools import wraps
import random
import string

from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password, identify_hasher
from sistema.models import Usuario


def require_role(roles_permitidos):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if 'usuario_rut' not in request.session:
                messages.error(request, 'Debes iniciar sesión para acceder a esta página.')
                return redirect('login')
            
            rol_actual = request.session.get('rol_id')
            if rol_actual not in roles_permitidos:
                messages.error(request, 'No tienes permisos para ver esta sección.')
                return redirect('login')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def login_view(request):
    if request.method == 'GET':
        storage = messages.get_messages(request)
        for _ in storage:
            pass
    
    if request.method == 'POST':
        credencial_ingresada = (
            request.POST.get('username') or ''
        ).strip()

        password_ingresada = request.POST.get('password') or ''

        if not credencial_ingresada or not password_ingresada:
            messages.error(
                request,
                'Debes ingresar tu correo o RUT y contraseña.'
            )
            return render(request, 'login.html')

        try:
            if '@' in credencial_ingresada:
                usuario = Usuario.objects.get(
                    correo__iexact=credencial_ingresada
                )
            else:
                usuario = Usuario.objects.get(
                    rut=credencial_ingresada
                )

            try:
                identify_hasher(usuario.password_hash)
                password_cifrada = True
            except ValueError:
                password_cifrada = False

            if password_cifrada:
                acceso_valido = check_password(
                    password_ingresada,
                    usuario.password_hash
                )
            else:
                acceso_valido = (
                    usuario.password_hash == password_ingresada
                )

                if acceso_valido:
                    usuario.password_hash = make_password(
                        password_ingresada
                    )
                    usuario.save(
                        update_fields=['password_hash']
                    )

            if acceso_valido:
                request.session['ultimo_acceso'] = datetime.now().strftime('%d/%m/%Y a las %H:%M')
                request.session.flush()

                request.session['usuario_rut'] = usuario.rut
                request.session['rol_id'] = usuario.rol_id_rol.id_rol
                request.session['nombre_usuario'] = usuario.nombre
                request.session['apellido_usuario'] = usuario.apellido_paterno
                request.session['rol_nombre'] = usuario.rol_id_rol.nombre_rol

                request.session['ultimo_acceso'] = datetime.now().strftime('%d/%m/%Y a las %H:%M')

                if usuario.cambiar_password:
                    request.session['debe_cambiar_pass'] = True
                    return redirect('cambiar_password_obligatorio')

                rol = usuario.rol_id_rol.id_rol
                if rol in [1, 4]:
                    return redirect('admin_inicio')
                elif rol == 2:
                    return redirect('profesor_inicio')
                elif rol == 3:
                    return redirect('apoderado_inicio')
                elif rol == 5:
                    return redirect('inicio_supervisor_aseo')

            else:
                messages.error(
                    request,
                    'Contraseña incorrecta.'
                )

        except Usuario.DoesNotExist:
            messages.error(
                request,
                'El usuario o correo ingresado no existe en el sistema.'
            )

        except Usuario.MultipleObjectsReturned:
            messages.error(
                request,
                'Hay más de una cuenta con ese correo. Contacta al administrador.'
            )

    return render(request, 'login.html')


def validar_rut(rut_str):
    if not rut_str:
        return False

    rut_limpio = str(rut_str).replace(".", "").replace("-", "").strip().upper()
    
    if len(rut_limpio) < 8 or len(rut_limpio) > 9:
        return False
    
    cuerpo = rut_limpio[:-1]
    dv = rut_limpio[-1]
    
    if not cuerpo.isdigit():
        return False
    
    suma = 0
    multiplicador = 2
    for digit in reversed(cuerpo):
        suma += int(digit) * multiplicador
        multiplicador = 2 if multiplicador == 7 else multiplicador + 1
    
    resto = suma % 11
    resultado = 11 - resto
    
    if resultado == 11:
        dv_esperado = '0'
    elif resultado == 10:
        dv_esperado = 'K'
    else:
        dv_esperado = str(resultado)
        
    return dv == dv_esperado


def cambiar_password_obligatorio(request):
    rut_usuario = request.session.get('usuario_rut')
    if not rut_usuario:
        return redirect('login')
        
    usuario = Usuario.objects.get(rut=rut_usuario)
    
    if request.method == 'POST':
        nueva_pass = request.POST.get('nueva_password')
        confirma_pass = request.POST.get('conf_password')
        correo_recup = request.POST.get('correo_recuperacion')
        
        if not nueva_pass or nueva_pass != confirma_pass:
            messages.error(request, "Las contraseñas no coinciden.")
            return render(request, 'cambiar_password.html', {'usuario': usuario})
            
        if not correo_recup:
            messages.error(request, "Debes ingresar tu correo de recuperación personal.")
            return render(request, 'cambiar_password.html', {'usuario': usuario})
            
        usuario.password_hash = make_password(nueva_pass)
        usuario.correo_recuperacion = correo_recup.strip().lower()
        usuario.cambiar_password = False
        usuario.save()
        
        request.session['debe_cambiar_pass'] = False
        
        messages.success(request, "¡Contraseña actualizada con éxito!")
        
        rol = usuario.rol_id_rol.id_rol
        if rol in [1, 4]:
            return redirect('admin_inicio')
        elif rol == 2:
            return redirect('profesor_inicio')
        elif rol == 3:
            return redirect('apoderado_inicio')
        elif rol == 5:
            return redirect('inicio_supervisor_aseo')
            
    return render(request, 'cambiar_password.html', {'usuario': usuario})


def cambiar_password_perfil(request):
    if 'usuario_rut' not in request.session:
        messages.error(request, 'Debes iniciar sesión para realizar esta acción.')
        return redirect('login')

    try:
        usuario = Usuario.objects.get(rut=request.session['usuario_rut'])
    except Usuario.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        pass_actual = request.POST.get('password_actual', '').strip()
        nueva_pass = request.POST.get('nueva_password', '').strip()
        conf_pass = request.POST.get('conf_password', '').strip()
        correo_recup = request.POST.get('correo_recuperacion', '').strip().lower()

        if not check_password(pass_actual, usuario.password_hash):
            messages.error(request, 'La contraseña actual es incorrecta.')
            return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

        if not nueva_pass or len(nueva_pass) < 6:
            messages.error(request, 'La nueva contraseña debe tener al menos 6 caracteres.')
            return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

        tiene_mayuscula = any(c.isupper() for c in nueva_pass)
        tiene_numero = any(c.isdigit() for c in nueva_pass)
        tiene_simbolo = any(not c.isalnum() for c in nueva_pass)

        if not (tiene_mayuscula and tiene_numero and tiene_simbolo):
            messages.error(request, 'La contraseña nueva debe contener al menos una letra mayúscula, un número y un símbolo especial.')
            return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

        if nueva_pass != conf_pass:
            messages.error(request, 'Las nuevas contraseñas ingresadas no coinciden.')
            return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})

        usuario.password_hash = make_password(nueva_pass)
        if correo_recup:
            usuario.correo_recuperacion = correo_recup
            
        usuario.save(update_fields=['password_hash', 'correo_recuperacion'])

        messages.success(request, '¡Tu contraseña y datos de seguridad han sido actualizados con éxito!')

        rol = usuario.rol_id_rol.id_rol
        if rol in [1, 4]:
            return redirect('admin_inicio')
        elif rol == 2:
            return redirect('profesor_inicio')
        elif rol == 3:
            return redirect('apoderado_inicio')
        elif rol == 5:
            return redirect('inicio_supervisor_aseo')

    return render(request, 'cambiar_password_perfil.html', {'usuario': usuario})


def recuperar_contrasena(request):
    if request.method == 'POST':
        correo_ingresado = request.POST.get('correo', '').strip().lower()
        
        try:
            usuario = Usuario.objects.get(correo=correo_ingresado)
            
            if not usuario.correo_recuperacion:
                messages.error(request, "Esta cuenta no tiene asociado un correo de recuperación personal. Contacte a soporte.")
                return render(request, 'recuperar_contrasena.html')
            
            caracteres = string.ascii_letters + string.digits
            temp_password = "".join(random.choice(caracteres) for _ in range(8))
            
            usuario.password_hash = make_password(temp_password)
            usuario.cambiar_password = True
            usuario.save()
            
            asunto = "Recuperación de Contraseña - SGE Santa Juliana"
            mensaje = (
                f"Hola {usuario.nombre or 'Usuario'},\n\n"
                f"Has solicitado restablecer tu contraseña.\n"
                f"Tu contraseña temporal de acceso es: {temp_password}\n\n"
                f"Al ingresar al sistema deberás cambiarla obligatoriamente.\n\n"
                f"Atentamente,\nSoporte TI - Colegio Santa Juliana"
            )
            
            send_mail(
                asunto,
                mensaje,
                None,
                [usuario.correo_recuperacion],
                fail_silently=False,
            )
            
            messages.success(request, "¡Instrucciones enviadas con éxito a tu correo de recuperación!")
            return redirect('login')
            
        except Usuario.DoesNotExist:
            messages.error(request, "No se encontró ninguna cuenta asociada a este correo institucional.")
            
    return render(request, 'recuperar_contrasena.html')