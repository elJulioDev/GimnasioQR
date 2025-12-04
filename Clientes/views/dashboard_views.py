import json
from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import CustomUser, Plan, Membership, AccessLog
from ..services.dashboard_service import AdminDashboardService

# --- VISTAS DE PANELES (con proteccion de rol) ---

@login_required(login_url='inicio_sesion')
def index_admin(request):
    """Panel de administrador optimizado usando Service Layer"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta area.')
        return redirect_by_role(request.user)
    
    # Instanciar el servicio
    service = AdminDashboardService()
    
    # Construir el contexto unificando todos los diccionarios
    context = {}
    context.update(service.get_kpis())
    context.update(service.get_user_stats())
    context.update(service.get_plan_stats())
    context.update(service.get_charts_data())
    context.update(service.get_attendance_details())
    context.update(service.get_transactions())
    
    return render(request, 'index_admin.html', context)

# ==================== FUNCION AUXILIAR ====================

def calcular_porcentaje_cambio(valor_anterior, valor_actual):
    """
    Calcula el porcentaje de cambio entre dos valores.
    Retorna un diccionario con el porcentaje y si es positivo o negativo.
    """
    if valor_anterior == 0:
        if valor_actual > 0:
            return {'porcentaje': 100, 'es_positivo': True}
        return {'porcentaje': 0, 'es_positivo': True}
    
    cambio = ((valor_actual - valor_anterior) / valor_anterior) * 100
    return {
        'porcentaje': abs(round(cambio, 1)),
        'es_positivo': cambio >= 0
    }


@login_required(login_url='inicio_sesion')
def index_moderador(request):
    """Panel de moderador con estadísticas y tendencias"""
    if not request.user.role or request.user.role != 'moderador':
        messages.error(request, 'No tienes permisos para acceder a esta área.')
        return redirect_by_role(request.user)
    
    from django.db.models import Count, Sum, Q
    from datetime import date, timedelta 
    
    today = timezone.now().date()

    # --- 1. Usuarios Activos y Tendencia ---
    usuarios_activos = CustomUser.objects.filter(
        role='socio',
        is_active_member=True
    ).count()
    
    # Calcular usuarios del mes pasado para la tendencia
    mes_pasado = today - timedelta(days=30)
    usuarios_mes_pasado = CustomUser.objects.filter(
        role='socio', 
        is_active_member=True,
        created_at__lte=mes_pasado
    ).count()
        
    # Calcular porcentaje (Lógica simplificada aquí mismo)
    cambio_usuarios = {'porcentaje': 0, 'es_positivo': True}
    if usuarios_mes_pasado > 0:
        diferencia = usuarios_activos - usuarios_mes_pasado
        porcentaje = (diferencia / usuarios_mes_pasado) * 100
        cambio_usuarios = {
            'porcentaje': abs(round(porcentaje, 1)),
            'es_positivo': porcentaje >= 0
        }
    elif usuarios_activos > 0:
        cambio_usuarios = {'porcentaje': 100, 'es_positivo': True}

    # --- 2. Accesos Hoy y Tendencia ---
    accesos_hoy = AccessLog.objects.filter(timestamp__date=today, status='allowed').count()
    
    ayer = today - timedelta(days=1)
    accesos_ayer = AccessLog.objects.filter(timestamp__date=ayer, status='allowed').count()
    
    # Necesitas tener la función 'calcular_porcentaje_cambio' definida o importada
    cambio_accesos = calcular_porcentaje_cambio(accesos_ayer, accesos_hoy)

    # --- 3. Planes por Vencer ---
    fecha_limite = today + timedelta(days=7)
    planes_vencer = Membership.objects.filter(
        is_active=True,
        end_date__gte=today,
        end_date__lte=fecha_limite
    ).count()
    
    # Comparación con la semana anterior
    semana_pasada_inicio = today - timedelta(days=7)
    semana_pasada_fin = today
    planes_venciendo_semana_pasada = Membership.objects.filter(
        is_active=True,
        end_date__gte=semana_pasada_inicio,
        end_date__lte=semana_pasada_fin
    ).count()
    
    cambio_planes = calcular_porcentaje_cambio(planes_venciendo_semana_pasada, planes_vencer)
    
    # --- 4. Tabla de Últimos Accesos (Dashboard) ---
    ultimos_accesos = AccessLog.objects.filter(
        timestamp__date=today
    ).select_related('user', 'membership', 'membership__plan').order_by('-timestamp')
    
    # --- 5. Lista de Usuarios para Gestión (Con último acceso) ---
    socios = CustomUser.objects.filter(role='socio').order_by('-created_at')
    lista_usuarios = []
    planes_renovacion = Plan.objects.filter(is_active=True).order_by('price')
    for socio in socios:
        # Intentamos obtener la membresía activa
        membership = socio.get_active_membership()
        
        # Obtener el último acceso permitido del usuario
        ultimo_acceso = AccessLog.objects.filter(user=socio, status='allowed').order_by('-timestamp').first()
        
        lista_usuarios.append({
            'user': socio,
            'plan_name': membership.plan.name if membership else 'Sin Plan Activo',
            'status_class': 'active' if socio.is_active_member else 'inactive',
            'status_text': 'Activo' if socio.is_active_member else 'Inactivo',
            'dias_restantes': membership.days_remaining() if membership else 0,
            'last_access': ultimo_acceso.timestamp if ultimo_acceso else None # Agregamos la fecha al contexto
        }) 
        
    context = {
        'usuarios_activos': usuarios_activos,
        'cambio_usuarios': cambio_usuarios, 
        'accesos_hoy': accesos_hoy,
        'cambio_accesos': cambio_accesos, # Enviamos cambio de accesos
        'planes_vencer': planes_vencer,
        'cambio_planes': cambio_planes,
        'ultimos_accesos': ultimos_accesos,
        'planes_renovacion': planes_renovacion,
        'lista_usuarios': lista_usuarios,
    }
    
    return render(request, 'index_moderador.html', context)

@login_required(login_url='inicio_sesion')
def index_socio(request):
    """Panel de socio con asistencias actualizadas"""
    if not request.user.role or request.user.role != 'socio':
        messages.error(request, 'No tienes permisos para acceder a esta área.')
        return redirect_by_role(request.user)
    
    # Obtener la membresía activa del socio
    membership = request.user.get_active_membership()
    
    # Obtener asistencias (últimos 30 días)
    from datetime import date, timedelta
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)
    
    # Todas las asistencias del último mes
    access_logs = request.user.access_logs.filter(
        timestamp__date__gte=thirty_days_ago,
        status='allowed'
    ).order_by('-timestamp')
    
    # Asistencias por semana
    seven_days_ago = today - timedelta(days=7)
    weekly_access = request.user.access_logs.filter(
        timestamp__date__gte=seven_days_ago,
        status='allowed'
    ).count()
    
    # Asistencias del mes actual
    primer_dia_mes = today.replace(day=1)
    monthly_access = request.user.access_logs.filter(
        timestamp__date__gte=primer_dia_mes,
        status='allowed'
    ).count()
    
    # Asistencias totales
    total_access = request.user.access_logs.filter(status='allowed').count()
    
    # Calcular racha (días consecutivos)
    streak_days = calculate_streak(request.user)
    
    # Acceso de hoy
    accessed_today = request.user.access_logs.filter(
        timestamp__date=today,
        status='allowed'
    ).exists()

    # === NUEVO CÓDIGO: Obtener planes para renovación ===
    planes_db = Plan.objects.filter(is_active=True).order_by('price')
    planes_data = []
    
    for plan in planes_db:
        # Procesar beneficios de texto (separar por comas)
        beneficios_extra = []
        if plan.benefits:
            beneficios_extra = [b.strip() for b in plan.benefits.split(',') if b.strip()]
            
        planes_data.append({
            'obj': plan,
            'beneficios_extra': beneficios_extra
        })
    
    context = {
        'user': request.user,
        'membership': membership,
        'has_active_membership': request.user.has_active_membership(),
        'access_logs': access_logs[:20],  # Mostrar últimas 20
        'weekly_access': weekly_access,
        'monthly_access': monthly_access,
        'total_access': total_access,
        'streak_days': streak_days,
        'accessed_today': accessed_today,
        'planes_renovacion': planes_data,
    }
    
    return render(request, 'index_socio.html', context)

@login_required(login_url='inicio_sesion')
def edit_profile_socio(request):
    """Vista para que el socio edite sus datos personales"""
    if not request.user.role or request.user.role != 'socio':
        messages.error(request, 'No tienes permisos para acceder a esta área.')
        return redirect_by_role(request.user)

    user = request.user

    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            
            # Validaciones básicas
            if not first_name or not last_name or not email:
                messages.error(request, 'Nombre, Apellido y Email son obligatorios.')
            else:
                # Verificar si el email cambió y si ya existe en otro usuario
                if email != user.email and CustomUser.objects.filter(email=email).exists():
                    messages.error(request, 'Este correo electrónico ya está en uso.')
                else:
                    # Guardar cambios
                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    user.phone = phone
                    user.save()
                    
                    messages.success(request, 'Perfil actualizado correctamente.')
                    return redirect('index_socio') # Redirigir al panel principal tras guardar

        except Exception as e:
            messages.error(request, f'Ocurrió un error al actualizar: {str(e)}')

    return render(request, 'edit_profile_socio.html', {'user': user})

def calculate_streak(user):
    """Calcula la racha de días consecutivos de asistencia"""
    from datetime import date, timedelta
    
    today = date.today()
    streak = 0
    current_date = today
    
    # Verificar los últimos 30 días
    for i in range(30):
        has_access = AccessLog.objects.filter(
            user=user,
            timestamp__date=current_date,
            status='allowed'
        ).exists()
        
        if has_access:
            streak += 1
            current_date -= timedelta(days=1)
        else:
            break
    
    return streak

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