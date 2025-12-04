import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from ..models import CustomUser, Plan, Membership
from ..utils import send_qr_email

def get_plans(request):
    """API endpoint para obtener los planes disponibles."""
    plans = Plan.objects.filter(is_active=True).values(
        'id', 'name', 'plan_type', 'description', 'price',
        'duration_days', 'access_days', 'includes_classes',
        'includes_nutritionist'
    )
    return JsonResponse({'success': True, 'plans': list(plans)})

def validate_rut(request):
    """API endpoint para validar RUT en tiempo real."""
    rut = request.GET.get('rut')
    if not rut:
        return JsonResponse({'valid': False, 'error': 'RUT no proporcionado'})
    exists = CustomUser.objects.filter(rut=rut).exists()
    return JsonResponse({
        'valid': not exists,
        'error': 'Este RUT ya esta registrado' if exists else None
    })

def validate_email(request):
    """API endpoint para validar email en tiempo real."""
    email = request.GET.get('email')
    if not email:
        return JsonResponse({'valid': False, 'error': 'Email no proporcionado'})
    exists = CustomUser.objects.filter(email=email).exists()
    return JsonResponse({
        'valid': not exists,
        'error': 'Este correo ya esta registrado' if exists else None
    })

@login_required(login_url='inicio_sesion')
def api_buscar_socio(request):
    """API para buscar socio y devolver TODOS los datos necesarios para el panel de pagos"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'success': False, 'error': 'Término de búsqueda vacío'})

    # Buscar usuario (RUT, Nombre o Email)
    user = CustomUser.objects.filter(
        Q(rut__icontains=query) | 
        Q(first_name__icontains=query) | 
        Q(last_name__icontains=query) |
        Q(email__icontains=query),
        role='socio'
    ).first()

    if user:
        # Obtener membresía activa
        membership = user.get_active_membership()
        
        # Calcular datos
        plan_actual = "Sin Plan Activo"
        fecha_inicio = "-"
        fecha_vencimiento = "-"
        dias_restantes = 0
        estado_badge = "Inactivo"

        if membership:
            plan_actual = membership.plan.name
            fecha_inicio = membership.start_date.strftime('%d/%m/%Y')
            fecha_vencimiento = membership.end_date.strftime('%d/%m/%Y')
            
            # Calcular días restantes reales
            delta = membership.end_date - timezone.now().date()
            dias_restantes = max(0, delta.days)
            estado_badge = "Activo"

        data = {
            'success': True,
            'user': {
                'rut': user.rut,
                'full_name': user.get_full_name(), # El JS espera 'full_name'
                'email': user.email,
                'initials': f"{user.first_name[:1]}{user.last_name[:1]}".upper(),
                'plan_actual': plan_actual,
                'fecha_inicio': fecha_inicio,
                'fecha_vencimiento': fecha_vencimiento,
                'dias_restantes': dias_restantes,
                'estado': estado_badge
            }
        }
        return JsonResponse(data)
    else:
        return JsonResponse({'success': False, 'error': 'Usuario no encontrado'})
    
@require_http_methods(["POST"])
@login_required(login_url='inicio_sesion')
def api_renovar_plan(request):
    """API para procesar la renovación o cambio de plan con lógica inteligente de fechas"""
    try:
        data = json.loads(request.body)
        
        # Obtener usuario según contexto
        if request.user.role == 'socio':
            user = request.user
        else:
            rut = data.get('rut')
            user = CustomUser.objects.get(rut=rut)

        plan_id = data.get('plan_id')
        payment_method = data.get('payment_method')
        notes = data.get('notes', '')

        # Nuevo plan seleccionado
        new_plan = Plan.objects.get(id=plan_id)

        # Fechas base
        today = timezone.now().date()
        
        # Buscar si tiene un plan VIGENTE (Activo y que vence hoy o después)
        current_membership = Membership.objects.filter(
            user=user, 
            is_active=True, 
            end_date__gte=today
        ).order_by('-end_date').first()
        
        # --- LÓGICA CORREGIDA DE FECHAS ---
        if current_membership:
            # CASO A: TIENE PLAN VIGENTE
            
            if current_membership.plan.id == new_plan.id:
                # Escenario 1: Es el MISMO plan -> RENOVACIÓN (Sumar días)
                # El nuevo empieza cuando termina el actual
                start_date = current_membership.end_date + timedelta(days=1)
                end_date = start_date + timedelta(days=new_plan.duration_days)
                
            else:
                # Escenario 2: Es OTRO plan -> CAMBIO DE PLAN (Mantener días)
                # "Los días actuales se deben mantener"
                
                # Empieza hoy (Reemplazo inmediato)
                start_date = today
                
                # Mantiene la fecha de vencimiento del plan anterior
                end_date = current_membership.end_date
                
                # IMPORTANTE: Cancelamos el plan anterior para que no se solapen como activos
                current_membership.status = 'cancelled'
                current_membership.is_active = False
                current_membership.notes = (current_membership.notes or "") + f" | Reemplazado por cambio a {new_plan.name} el {today}"
                current_membership.save()
                
        else:
            # CASO B: PLAN CADUCADO O SIN PLAN
            # "Debe tener los días que otorga el plan de vuelta"
            start_date = today
            end_date = start_date + timedelta(days=new_plan.duration_days)

        # -----------------------------------

        # Crear la nueva membresía con las fechas calculadas
        membership = Membership.objects.create(
            user=user,
            plan=new_plan,
            start_date=start_date,
            end_date=end_date,
            payment_method=payment_method,
            amount_paid=new_plan.price, # Se registra el pago del nuevo plan
            status='active',
            is_active=True,
            notes=f"Gestión por: {request.user.get_full_name()} | {notes}"
        )

        # Actualizar estado del usuario
        user.is_active_member = True
        user.save()

        # Enviar correos si corresponde
        send_qr = data.get('send_qr', False)
        send_contract = data.get('send_contract', False)

        if send_qr or send_contract:
            try:
                send_qr_email(user, membership, send_qr=send_qr, send_contract=send_contract)
            except Exception as e:
                print(f"Error enviando email: {e}")

        return JsonResponse({'success': True, 'message': 'Plan procesado correctamente'})

    except CustomUser.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuario no encontrado'}, status=404)
    except Plan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Plan no encontrado'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@require_http_methods(["POST"])
@login_required(login_url='inicio_sesion')
def api_crear_socio_moderador(request):
    """API que procesa el formulario del moderador"""
    try:
        data = json.loads(request.body)
        
        # 1. Validaciones básicas
        if CustomUser.objects.filter(rut=data['rut']).exists():
            return JsonResponse({'success': False, 'error': 'El RUT ya existe'})
        if CustomUser.objects.filter(email=data['email']).exists():
            return JsonResponse({'success': False, 'error': 'El Email ya existe'})

        # 2. Crear Usuario
        user = CustomUser.objects.create_user(
            username=data['rut'],
            rut=data['rut'],
            email=data['email'],
            password=data['rut'], # Contraseña inicial es el RUT
            first_name=data['firstName'],
            last_name=data['lastName'],
            phone=data.get('phone', ''),
            birthdate=data.get('birthdate') or None,
            role='socio',
            is_active=True,
            is_active_member=False # Se activará al crear la membresía abajo
        )

        # 3. Generar QR
        user.generate_qr_code()
        user.save()

        # 4. Crear Membresía
        plan = Plan.objects.get(plan_type=data['plan'])
        start_date = timezone.now().date()
        
        membership = Membership.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            payment_method=data.get('paymentMethod', 'efectivo'),
            amount_paid=plan.price,
            status='active',
            is_active=True,
            notes=f"Creado por moderador: {request.user.get_full_name()}"
        )
        
        user.is_active_member = True
        user.save()

        # 5. Enviar Email (Opcional)
        if data.get('sendQREmail'):
            try:
                send_qr_email(user, membership)
            except:
                pass # No detener el proceso si falla el email

        return JsonResponse({'success': True})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
@require_http_methods(["POST"])
@login_required(login_url='inicio_sesion')
def api_cancelar_plan(request):
    """API para que el socio cancele su plan actual inmediatamente"""
    try:
        user = request.user
        membership = user.get_active_membership()

        if not membership:
            return JsonResponse({'success': False, 'error': 'No tienes un plan activo para cancelar.'})

        # Cancelar membresía
        membership.status = 'cancelled'
        membership.is_active = False
        membership.notes = (membership.notes or "") + f" | Cancelado por el usuario el {timezone.now().strftime('%Y-%m-%d')}"
        membership.save()

        # Actualizar estado del usuario
        user.is_active_member = False
        user.save()

        return JsonResponse({'success': True, 'message': 'Plan cancelado exitosamente.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)