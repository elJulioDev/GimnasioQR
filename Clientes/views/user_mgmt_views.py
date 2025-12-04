import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import datetime
from ..utils import send_qr_email
from ..models import CustomUser, Plan, Membership

# ==================== GESTION DE USUARIOS (ADMIN) ====================

@login_required(login_url='inicio_sesion')
def admin_user_details(request, user_id):
    """Ver detalles completos de un usuario - Solo admin"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta area.')
        return redirect('index_admin')
    
    try:
        user = CustomUser.objects.get(id=user_id, is_superuser=False)
        
        # Obtener membresias del usuario
        memberships = user.memberships.all().select_related('plan').order_by('-created_at')
        
        # Obtener accesos recientes (últimos 20)
        access_logs = user.access_logs.all().order_by('-timestamp')[:20]
        
        # Calcular estadisticas
        total_accesos = user.access_logs.count()
        accesos_permitidos = user.access_logs.filter(status='allowed').count()
        accesos_denegados = user.access_logs.filter(status='denied').count()
        
        context = {
            'user_detail': user,
            'memberships': memberships,
            'access_logs': access_logs,
            'total_accesos': total_accesos,
            'accesos_permitidos': accesos_permitidos,
            'accesos_denegados': accesos_denegados,
        }
        
        return render(request, 'admin_user_details.html', context)
    
    except CustomUser.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('index_admin')
    
@login_required(login_url='inicio_sesion')
def admin_user_edit(request, user_id):
    """Editar usuario - Solo admin (Versión Corregida)"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta área.')
        return redirect('index_admin')
    
    try:
        user = CustomUser.objects.get(id=user_id, is_superuser=False)
        current_membership = user.get_active_membership()
        if not current_membership:
            current_membership = user.memberships.order_by('-created_at').first()

        if request.method == 'GET':
            planes = Plan.objects.filter(is_active=True).order_by('price')
            context = {
                'user_edit': user,
                'planes': planes,
                'current_membership': current_membership
            }
            return render(request, 'admin_user_edit.html', context)
        
        elif request.method == 'POST':
            # 1. Actualizar Datos Básicos
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.email = request.POST.get('email', user.email)
            user.phone = request.POST.get('phone', user.phone)
            
            if CustomUser.objects.exclude(id=user_id).filter(email=user.email).exists():
                messages.error(request, 'El email ya está en uso por otro usuario')
                return redirect('admin_user_edit', user_id=user.id)
            
            birthdate = request.POST.get('birthdate')
            if birthdate:
                user.birthdate = birthdate
            
            new_role = request.POST.get('role')
            if new_role in ['socio', 'moderador', 'admin']:
                user.role = new_role
            
            user.is_active = 'is_active' in request.POST
            
            # 2. Gestión de Membresía
            if user.role == 'socio':
                user.is_active_member = 'is_active_member' in request.POST
                
                plan_id = request.POST.get('plan_id')
                start_date_str = request.POST.get('membership_start')
                end_date_str = request.POST.get('membership_end')
                
                if plan_id:
                    try:
                        plan = Plan.objects.get(id=plan_id)
                        
                        # --- CORRECCIÓN 1: Convertir texto a objetos Fecha ---
                        start_date_obj = None
                        if start_date_str:
                            start_date_obj = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                            
                        end_date_obj = None
                        if end_date_str:
                            end_date_obj = datetime.strptime(end_date_str, '%Y-%m-%d').date()

                        # Lógica de actualización o creación
                        if current_membership:
                            current_membership.plan = plan
                            if start_date_obj: current_membership.start_date = start_date_obj
                            if end_date_obj: current_membership.end_date = end_date_obj
                            
                            # Forzar estado activo si las fechas son válidas
                            if end_date_obj:
                                # Verificamos si la fecha es válida (futura o hoy)
                                if end_date_obj >= timezone.now().date():
                                    # Si las fechas están bien, RESPETAMOS lo que decidió el admin en el checkbox (user.is_active_member)
                                    if user.is_active_member:
                                        current_membership.status = 'active'
                                        current_membership.is_active = True
                                    else:
                                        # Si el admin desmarcó la casilla, ponemos la membresía como inactiva aunque las fechas sirvan
                                        current_membership.status = 'inactive'
                                        current_membership.is_active = False
                                else:
                                    # Si la fecha ya pasó, se vence automáticamente
                                    current_membership.status = 'expired'
                                    current_membership.is_active = False
                            
                            current_membership.save()
                        else:
                            if start_date_obj and end_date_obj:
                                Membership.objects.create(
                                    user=user,
                                    plan=plan,
                                    start_date=start_date_obj,
                                    end_date=end_date_obj,
                                    payment_method='efectivo',
                                    amount_paid=plan.price,
                                    status='active',
                                    is_active=True,
                                    notes=f"Membresía creada manualmente por Admin"
                                )
                    except Plan.DoesNotExist:
                        pass
            else:
                user.is_active_member = False
            
            # --- CORRECCIÓN 2: Esto ahora está FUERA del else, se ejecuta siempre ---
            new_password = request.POST.get('password')
            if new_password:
                user.set_password(new_password)
            
            user.save()
            
            messages.success(request, f'Usuario {user.get_full_name()} actualizado correctamente')
            return redirect('admin_user_details', user_id=user.id)
    
    except CustomUser.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('index_admin')
    

@login_required(login_url='inicio_sesion')
def admin_user_delete(request, user_id):
    """Eliminar usuario - Solo admin"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta area.')
        return redirect('index_admin')
    
    try:
        user = CustomUser.objects.get(id=user_id, is_superuser=False)
        
        if request.method == 'GET':
            # Mostrar pagina de confirmacion
            # Obtener informacion relevante antes de eliminar
            memberships_count = user.memberships.count()
            access_logs_count = user.access_logs.count()
            
            context = {
                'user_delete': user,
                'memberships_count': memberships_count,
                'access_logs_count': access_logs_count,
            }
            return render(request, 'admin_user_delete.html', context)
        
        elif request.method == 'POST':
            # Confirmar eliminacion
            user_name = user.get_full_name()
            user_rut = user.rut
            user.delete()
            
            messages.success(request, f'Usuario {user_name} ({user_rut}) eliminado correctamente')
            return redirect('index_admin')
    
    except CustomUser.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('index_admin')

@login_required(login_url='inicio_sesion')
def admin_user_create(request):
    """Crear nuevo usuario desde panel admin"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta area.')
        return redirect('index_admin')
    
    if request.method == 'GET':
        # Mostrar formulario de creacion
        plans = Plan.objects.filter(is_active=True)
        context = {
            'plans': plans,
            'is_admin_creation': True
        }
        return render(request, 'admin_user_create.html', context)
    
    elif request.method == 'POST':
        return process_admin_user_creation(request)

def process_admin_user_creation(request):
    """Procesa la creacion de usuario por el admin"""
    if not request.user.role or request.user.role != 'admin':
        return JsonResponse({
            'success': False,
            'error': 'No autorizado'
        }, status=403)
    
    try:
        # Manejar tanto JSON como POST
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        # Validar campos obligatorios
        required_fields = ['rut', 'firstName', 'lastName', 'email', 'password', 'role']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return JsonResponse({
                'success': False,
                'error': f'Campos requeridos faltantes: {", ".join(missing_fields)}'
            }, status=400)
        
        # Validar duplicados
        if CustomUser.objects.filter(rut=data['rut']).exists():
            return JsonResponse({'success': False, 'error': 'El RUT ingresado ya esta registrado'}, status=400)
        
        if CustomUser.objects.filter(email=data['email']).exists():
            return JsonResponse({'success': False, 'error': 'El correo electronico ya esta registrado'}, status=400)
        
        # Crear el usuario
        user = CustomUser.objects.create_user(
            username=data['rut'],
            email=data['email'],
            password=data['password'],
            first_name=data['firstName'],
            last_name=data['lastName'],
            rut=data['rut'],
            phone=data.get('phone', ''),
            birthdate=data.get('birthdate') or None,
            role=data['role'],
            is_active=True,
            is_active_member=False
        )
        
        # Lógica para Socios
        if data['role'] == 'socio' and data.get('plan'):
            try:
                plan = Plan.objects.get(plan_type=data['plan'])
                
                # Generar QR
                user.refresh_from_db()
                if not user.qr_code:
                    user.generate_qr_code()
                    user.refresh_from_db()
                
                # Crear membresía
                start_date = timezone.now().date()
                membership = Membership.objects.create(
                    user=user,
                    plan=plan,
                    start_date=start_date,
                    payment_method=data.get('paymentMethod', 'efectivo'),
                    amount_paid=plan.price,
                    status='active',
                    is_active=True,
                    notes=f"Registro administrativo por {request.user.get_full_name()}"
                )
                
                # --- EMAIL Y CONTRATO ---
                # Capturamos los flags del frontend
                send_qr_req = data.get('sendQREmail', False)
                send_contract_req = data.get('sendContract', False) # <--- NUEVO

                email_sent = False
                if send_qr_req or send_contract_req:
                    try:
                        email_sent = send_qr_email(
                            user, 
                            membership, 
                            send_qr=send_qr_req, 
                            send_contract=send_contract_req
                        )
                    except Exception as email_error:
                        print(f"Error al enviar email: {str(email_error)}")
                
                msg_extra = []
                if send_qr_req: msg_extra.append("QR")
                if send_contract_req: msg_extra.append("Contrato")
                msg_final = f" (+ {' y '.join(msg_extra)} enviado)" if msg_extra else ""

                return JsonResponse({
                    'success': True,
                    'message': f'Socio creado correctamente{msg_final}',
                    'user_id': user.id
                })
                    
            except Plan.DoesNotExist:
                user.delete()
                return JsonResponse({'success': False, 'error': f'Plan "{data.get("plan")}" no encontrado'}, status=400)
        else:
            return JsonResponse({
                'success': True,
                'message': f'Usuario {user.role.capitalize()} creado correctamente',
                'user_id': user.id
            })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al crear usuario: {str(e)}'
        }, status=500)

@login_required(login_url='inicio_sesion')
def moderador_nuevo_usuario(request):
    """Renderiza el HTML separado para crear usuario"""
    # Verificar que sea moderador o admin
    if not request.user.role in ['moderador', 'admin']:
        messages.error(request, 'No tienes permisos.')
        return redirect('inicio_sesion')
    
    # Obtener planes para llenar el select del formulario
    planes = Plan.objects.filter(is_active=True).order_by('price')
    
    return render(request, 'moderador_nuevo_usuario.html', {'planes': planes})

@login_required(login_url='inicio_sesion')
def moderador_ver_usuario(request, user_id):
    """Vista para que el moderador vea detalles de un socio"""
    # 1. Verificar permisos
    if request.user.role not in ['moderador', 'admin']:
        messages.error(request, 'No tienes permisos.')
        return redirect('index_moderador')

    try:
        # 2. Buscar usuario
        user = CustomUser.objects.get(id=user_id)
        
        # 3. Obtener datos relacionados
        memberships = user.memberships.all().order_by('-created_at')
        access_logs = user.access_logs.all().order_by('-timestamp')[:20]
        
        context = {
            'user_detail': user,
            'memberships': memberships,
            'access_logs': access_logs,
            'total_accesos': user.access_logs.count(),
            'accesos_permitidos': user.access_logs.filter(status='allowed').count(),
            'accesos_denegados': user.access_logs.filter(status='denied').count(),
        }
        # Renderizar el HTML específico de moderador
        return render(request, 'moderador_user_details.html', context) 

    except CustomUser.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('index_moderador')

@login_required(login_url='inicio_sesion')
def moderador_editar_usuario(request, user_id):
    """Vista para que el moderador edite un socio"""
    if request.user.role not in ['moderador', 'admin']:
        messages.error(request, 'No tienes permisos.')
        return redirect('index_moderador')

    try:
        user = CustomUser.objects.get(id=user_id)

        if request.method == 'POST':
            # Actualizar datos básicos
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            user.phone = request.POST.get('phone')
            
            # Moderador solo edita estado de membresía si es socio
            if user.role == 'socio':
                 user.is_active_member = request.POST.get('is_active_member') == 'on'

            # Contraseña opcional
            new_pass = request.POST.get('password')
            if new_pass:
                user.set_password(new_pass)

            user.save()
            messages.success(request, 'Usuario actualizado correctamente')
            return redirect('moderador_ver_usuario', user_id=user.id)

        # Renderizar el HTML específico de edición para moderador
        return render(request, 'moderador_user_edit.html', {'user_edit': user})

    except CustomUser.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('index_moderador')

@require_http_methods(["POST"])
@login_required(login_url='inicio_sesion')
def moderador_eliminar_usuario(request, user_id):
    """Vista para eliminar usuario desde panel moderador"""
    if request.user.role not in ['moderador', 'admin']:
        messages.error(request, 'No tienes permisos.')
        return redirect('index_moderador')

    try:
        user = CustomUser.objects.get(id=user_id)
        nombre = user.get_full_name()
        
        # Seguridad: No borrar admins ni a uno mismo
        if user.role == 'admin' or user.id == request.user.id:
            messages.error(request, 'No puedes eliminar a este usuario.')
            return redirect('index_moderador')

        user.delete()
        messages.success(request, f'Usuario {nombre} eliminado correctamente.')
        return redirect('index_moderador')

    except CustomUser.DoesNotExist:
        messages.error(request, 'Usuario no encontrado')
        return redirect('index_moderador')