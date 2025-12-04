import json
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import CustomUser, Plan, Membership
from ..utils import send_qr_email

# --- VISTAS DE AUTENTICACIONN ---

def inicio_sesion(request):
    """
    Vista de inicio de sesion que maneja GET y POST.
    """
    # CAMBIO: Verificar que el usuario tenga rol antes de redirigir
    if request.user.is_authenticated:
        # Si es superusuario, cerrar sesion y mostrar error
        if request.user.is_superuser:
            logout(request)
            messages.error(request, 'Los superusuarios deben acceder por /admin')
            return render(request, 'IniciarSesion.html')
        
        # Si no tiene rol, cerrar sesion y mostrar error
        if not request.user.role:
            logout(request)
            messages.error(request, 'Usuario sin rol asignado. Contacte al administrador.')
            return render(request, 'IniciarSesion.html')
        
        # Si tiene rol, redirigir normalmente
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        return process_login(request)
    
    return render(request, 'IniciarSesion.html')

@require_http_methods(["POST"])
def process_login(request):
    """
    Procesa el login con RUT o Email y contraseña.
    BLOQUEA superusuarios para que NO puedan entrar por la web.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return JsonResponse({
                'success': False,
                'error': 'Por favor ingresa tu RUT/Email y contraseña'
            }, status=400)
        
        # Autenticar usuario
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # BLOQUEAR SUPERUSUARIOS - NO pueden entrar por la web
            if user.is_superuser:
                return JsonResponse({
                    'success': False,
                    'error': 'Los superusuarios solo pueden acceder por /admin'
                }, status=403)
            
            # BLOQUEAR usuarios sin rol (seguridad adicional)
            if not user.role:
                return JsonResponse({
                    'success': False,
                    'error': 'Usuario sin rol asignado. Contacte al administrador.'
                }, status=403)
            
            # Login exitoso para usuarios normales
            login(request, user)
            
            redirect_url = get_redirect_url_by_role(user)
            
            return JsonResponse({
                'success': True,
                'message': 'Inicio de sesion exitoso',
                'redirect_url': redirect_url,
                'user': {
                    'id': user.id,
                    'name': user.get_full_name(),
                    'role': user.role,
                    'email': user.email
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'RUT/Email o contraseña incorrectos'
            }, status=401)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar el inicio de sesion: {str(e)}'
        }, status=500)

def get_redirect_url_by_role(user):
    """
    Retorna la URL de redireccion según el rol del usuario.
    """
    role_urls = {
        'admin': '/admin-panel/',
        'moderador': '/moderador-panel/',
        'socio': '/socio-panel/',
    }
    # CAMBIO: Si no tiene rol, ir a una pagina de error en lugar de loop
    return role_urls.get(user.role, '/error-sin-rol/')

def redirect_by_role(user):
    """
    Redirige al usuario según su rol.
    """
    # CAMBIO: Manejar usuarios sin rol sin crear loop
    if not user.role:
        # Cerrar sesion de usuarios sin rol
        logout(user)
        return redirect('inicio_sesion')
    
    role_redirects = {
        'admin': redirect('index_admin'),
        'moderador': redirect('index_moderador'),
        'socio': redirect('index_socio'),
    }
    
    # Si el rol no esta en el diccionario, ir a inicio_sesion
    # Pero solo si el usuario NO esta ya en inicio_sesion
    return role_redirects.get(user.role, redirect('inicio_sesion'))

def cerrar_sesion(request):
    """
    Cierra la sesion del usuario y redirige al login.
    """
    logout(request)
    messages.success(request, 'Has cerrado sesion exitosamente.')
    return redirect('inicio_sesion')

def landing_page(request):
    """
    Vista para la página de inicio (Landing Page).
    Muestra planes, información del gimnasio y ubicación.
    """
    # Si el usuario ya está logueado, lo redirigimos a su panel correspondiente
    if request.user.is_authenticated:
        return redirect_by_role(request.user)

    # Obtener planes activos para mostrar en la sección de precios
    planes = Plan.objects.filter(is_active=True).order_by('price')
    
    return render(request, 'landing.html', {
        'planes': planes
    })

def mostrar_registro(request):
    """Vista para el registro de nuevos socios."""
    if request.method == 'GET':
        plans = Plan.objects.filter(is_active=True)
        context = {'plans': plans}
        return render(request, 'Registrarse.html', context)
    elif request.method == 'POST':
        return process_registration(request)

@require_http_methods(["POST"])
def process_registration(request):
    """Procesa el registro completo del usuario con plan y pago."""
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else request.POST
        
        required_fields = ['rut', 'firstName', 'lastName', 'email', 'phone',
                          'password', 'birthdate', 'plan', 'paymentMethod']
        
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'success': False,
                    'error': f'El campo {field} es requerido'
                }, status=400)
        
        if CustomUser.objects.filter(rut=data['rut']).exists():
            return JsonResponse({
                'success': False,
                'error': 'El RUT ingresado ya esta registrado'
            }, status=400)
        
        if CustomUser.objects.filter(email=data['email']).exists():
            return JsonResponse({
                'success': False,
                'error': 'El correo electronico ya esta registrado'
            }, status=400)
        
        try:
            plan = Plan.objects.get(plan_type=data['plan'])
        except Plan.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Plan no valido'
            }, status=400)
        
        # Crear el usuario
        user = CustomUser.objects.create_user(
            username=data['rut'],
            email=data['email'],
            password=data['password'],
            first_name=data['firstName'],
            last_name=data['lastName'],
            rut=data['rut'],
            phone=data['phone'],
            birthdate=data['birthdate'],
            role='socio',
            is_active=True,
            is_active_member=False
        )
        
        # IMPORTANTE: Refrescar el usuario desde la BD
        # Esto asegura que el QR fue generado en el save()
        user.refresh_from_db()
        
        # Si el QR no se genero automaticamente, generarlo manualmente
        if not user.qr_code:
            user.generate_qr_code()
            user.refresh_from_db()

        # Crear la membresia
        start_date = timezone.now().date()
        membership = Membership.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            payment_method=data['paymentMethod'],
            amount_paid=plan.price,
            status='active',
            is_active=True,
            notes=f"Registro inicial - Pago mediante {data['paymentMethod']}"
        )
        
        # --- LÓGICA ACTUALIZADA DE EMAIL ---
        email_sent = False
        # Capturamos los checkbox del frontend
        send_qr_req = data.get('sendQREmail', False)
        send_contract_req = data.get('sendContract', False)

        # Si se solicitó al menos uno de los dos
        if send_qr_req or send_contract_req:
            try:
                # Pasamos ambos flags explícitamente
                email_sent = send_qr_email(
                    user, 
                    membership, 
                    send_qr=send_qr_req, 
                    send_contract=send_contract_req
                )
            except Exception as email_error:
                print(f"Error email: {str(email_error)}")
                email_sent = False
        
        user.backend = 'Clientes.backends.RUTorEmailBackend'
        login(request, user)
        
        return JsonResponse({
            'success': True,
            'message': 'Registro exitoso',
            'user_id': user.id,
            'qr_code_url': user.qr_code.url if user.qr_code else None,
            'email_sent': email_sent
        })
        
    except Exception as e:
        print(f"Error en registro: {str(e)}")  # Debug
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar el registro: {str(e)}'
        }, status=500)

def get_plans(request):
    """API endpoint para obtener los planes disponibles."""
    plans = Plan.objects.filter(is_active=True).values(
        'id', 'name', 'plan_type', 'description', 'price',
        'duration_days', 'access_days', 'includes_classes',
        'includes_nutritionist'
    )
    return JsonResponse({'success': True, 'plans': list(plans)})

@require_http_methods(["POST"])
@login_required(login_url='inicio_sesion')
def verify_password(request):
    """API para verificar la contraseña actual (Paso 1 del modal)"""
    try:
        data = json.loads(request.body)
        current_password = data.get('password', '')
        
        # Verificar contraseña
        if request.user.check_password(current_password):
            return JsonResponse({'valid': True})
        else:
            return JsonResponse({'valid': False, 'error': 'La contraseña ingresada es incorrecta.'})
            
    except Exception as e:
        return JsonResponse({'valid': False, 'error': f'Error de servidor: {str(e)}'}, status=500)

@require_http_methods(["POST"])
@login_required(login_url='inicio_sesion')
def change_password_socio(request):
    """API para guardar la nueva contraseña (Paso 2 del modal)"""
    try:
        data = json.loads(request.body)
        user = request.user
        
        new_password = data.get('new_password')
        confirm_password = data.get('confirm_password')
        
        # Validaciones del servidor
        if new_password != confirm_password:
            return JsonResponse({'success': False, 'error': 'Las nuevas contraseñas no coinciden.'})
            
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'La contraseña debe tener al menos 8 caracteres.'})

        # Guardar nueva contraseña
        user.set_password(new_password)
        user.save()
        
        # IMPORTANTE: Mantener la sesión activa después del cambio
        update_session_auth_hash(request, user)
        
        return JsonResponse({'success': True, 'message': 'Contraseña actualizada correctamente.'})

    except Exception as e:
        print(f"Error cambiando password: {e}") # Esto saldrá en tu consola de comandos para debug
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)
    