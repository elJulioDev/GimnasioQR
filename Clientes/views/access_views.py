import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from ..models import CustomUser, AccessLog

@require_http_methods(["POST"])
def process_qr_scan(request):
    """
    Procesa el escaneo de QR y registra el acceso del usuario.
    CORREGIDO: Usa rango de fechas para evitar error de timezone en MySQL.
    """
    try:
        # Obtener datos del QR
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        qr_data = data.get('qr_data')
        
        if not qr_data:
            return JsonResponse({'success': False, 'error': 'No se proporcionó información del QR'}, status=400)
        
        # --- PARSEO DE DATOS (Igual que antes) ---
        user_id, qr_id, rut = None, None, None
        try:
            if isinstance(qr_data, str):
                import ast
                qr_dict = ast.literal_eval(qr_data.strip())
                user_id = qr_dict.get('user_id')
                qr_id = qr_dict.get('qr_id')
                rut = qr_dict.get('rut')
            elif isinstance(qr_data, dict):
                user_id = qr_data.get('user_id')
                qr_id = qr_data.get('qr_id')
                rut = qr_data.get('rut')
            else:
                qr_dict = json.loads(qr_data)
                user_id = qr_dict.get('user_id')
                qr_id = qr_dict.get('qr_id')
                rut = qr_dict.get('rut')
                
            if not user_id or not qr_id or not rut:
                raise ValueError("Datos incompletos")
        except Exception:
            return JsonResponse({'success': False, 'error': 'Formato QR inválido'}, status=400)
        
        # Buscar usuario
        try:
            user = CustomUser.objects.get(id=user_id, rut=rut, qr_unique_id=qr_id)
        except CustomUser.DoesNotExist:
            return JsonResponse({
                'success': False, 
                'status': 'denied', 
                'error': 'Usuario no encontrado o QR inválido',
                'user': {'name': 'Desconocido', 'rut': rut or 'N/A'}
            }, status=404)
        
        # Verificar membresía
        membership = user.get_active_membership()
        if not membership or not membership.is_valid():
            AccessLog.objects.create(user=user, status='denied', membership=membership, denial_reason='Membresía vencida')
            return JsonResponse({
                'success': False,
                'status': 'denied',
                'error': 'Membresía vencida o inexistente',
                'user': {'name': user.get_full_name(), 'rut': user.rut}
            })
        
        # CORRECCIÓN PRINCIPAL: FILTRO POR RANGO HORARIO
        
        # 1. Obtenemos la hora actual en Chile
        now_chile = timezone.localtime(timezone.now())
        
        # 2. Definimos el inicio (00:00:00) y fin (23:59:59) del día actual
        start_of_day = now_chile.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now_chile.replace(hour=23, minute=59, second=59, microsecond=999999)

        # 3. Buscamos registros usando el rango (__range) en lugar de __date
        already_accessed_today = AccessLog.objects.filter(
            user=user,
            timestamp__range=(start_of_day, end_of_day), # <--- AQUÍ ESTÁ EL CAMBIO
            status='allowed'
        ).exists()
        
        if already_accessed_today:
            # Obtener el registro para mostrar la hora
            todays_access = AccessLog.objects.filter(
                user=user,
                timestamp__range=(start_of_day, end_of_day),
                status='allowed'
            ).first()
            
            # Recalcular estadísticas para mostrar en el frontend
            # (Simplificado para brevedad, usa tu lógica original si prefieres)
            primer_dia_mes = now_chile.replace(day=1, hour=0, minute=0, second=0)
            monthly_access = AccessLog.objects.filter(user=user, timestamp__gte=primer_dia_mes, status='allowed').count()
            
            return JsonResponse({
                'success': False,
                'status': 'denied',
                'error': f'Ya registraste entrada a las {timezone.localtime(todays_access.timestamp).strftime("%H:%M:%S")}',
                'already_accessed_today': True,
                'user': {
                    'name': user.get_full_name(),
                    'rut': user.rut,
                    'monthly_access': monthly_access,
                    'access_time': timezone.localtime(todays_access.timestamp).strftime('%H:%M:%S')
                }
            }, status=403)
        
        # CREAR NUEVO REGISTRO
        access_log = AccessLog.objects.create(
            user=user,
            status='allowed',
            membership=membership
        )
        
        # Estadísticas finales
        primer_dia_mes = now_chile.replace(day=1, hour=0, minute=0, second=0)
        monthly_access = AccessLog.objects.filter(user=user, timestamp__gte=primer_dia_mes, status='allowed').count()
        
        return JsonResponse({
            'success': True,
            'status': 'allowed',
            'message': '¡Bienvenido!',
            'already_accessed_today': False,
            'user': {
                'name': user.get_full_name(),
                'rut': user.rut,
                'monthly_access': monthly_access,
                'access_time': timezone.localtime(access_log.timestamp).strftime('%H:%M:%S')
            }
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
def mostrar_Scanner(request):
    """Esta vista renderiza la pagina del Scanner."""
    return render(request, 'QR_Scanner.html')

def mostrar_QRCodeEmail(request):
    """Esta vista renderiza la pagina email."""
    return render(request, 'qr_code_email.html')