from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from ..models import CustomUser, Plan, Membership, AccessLog
from ..services.dashboard_service import AdminDashboardService
from datetime import timedelta

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
    """Panel de moderador con estadísticas y tendencias - CORREGIDO ZONA HORARIA"""
    if not request.user.role or request.user.role != 'moderador':
        messages.error(request, 'No tienes permisos para acceder a esta área.')
        return redirect_by_role(request.user)
    
    from django.db.models import Count, Sum, Q
    
    # --- FECHAS CON ZONA HORARIA (CHILE) ---
    now_chile = timezone.localtime(timezone.now())
    today = now_chile.date()

    # Definir rangos exactos para HOY
    start_of_day = now_chile.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now_chile.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Definir rangos exactos para AYER
    yesterday_date = now_chile - timedelta(days=1)
    start_of_yesterday = yesterday_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_yesterday = yesterday_date.replace(hour=23, minute=59, second=59, microsecond=999999)

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
        
    # Calcular porcentaje
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
    # CORRECCIÓN: Usar rangos (timestamp__range) en lugar de __date
    accesos_hoy = AccessLog.objects.filter(
        timestamp__range=(start_of_day, end_of_day), 
        status='allowed'
    ).count()
    
    accesos_ayer = AccessLog.objects.filter(
        timestamp__range=(start_of_yesterday, end_of_yesterday), 
        status='allowed'
    ).count()
    
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
    # CORRECCIÓN: Mostrar accesos de hoy usando el rango correcto
    ultimos_accesos = AccessLog.objects.filter(
        timestamp__range=(start_of_day, end_of_day)
    ).select_related('user', 'membership', 'membership__plan').order_by('-timestamp')
    
    # --- 5. Lista de Usuarios para Gestión ---
    socios = CustomUser.objects.filter(role='socio').order_by('-created_at')
    lista_usuarios = []
    planes_renovacion = Plan.objects.filter(is_active=True).order_by('price')
    for socio in socios:
        membership = socio.get_active_membership()
        
        ultimo_acceso = AccessLog.objects.filter(user=socio, status='allowed').order_by('-timestamp').first()
        
        lista_usuarios.append({
            'user': socio,
            'plan_name': membership.plan.name if membership else 'Sin Plan Activo',
            'status_class': 'active' if socio.is_active_member else 'inactive',
            'status_text': 'Activo' if socio.is_active_member else 'Inactivo',
            'dias_restantes': membership.days_remaining() if membership else 0,
            'last_access': ultimo_acceso.timestamp if ultimo_acceso else None
        }) 
        
    context = {
        'usuarios_activos': usuarios_activos,
        'cambio_usuarios': cambio_usuarios, 
        'accesos_hoy': accesos_hoy,
        'cambio_accesos': cambio_accesos,
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
    
    # === CORRECCIÓN DE FECHAS ===
    # Usamos timezone.localtime para obtener la hora real en Chile
    now_chile = timezone.localtime(timezone.now())
    
    # 1. Asistencias (últimos 30 días)
    # Calculamos la fecha de inicio hace 30 días a las 00:00:00
    thirty_days_ago = now_chile - timedelta(days=30)
    thirty_days_ago_start = thirty_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Usamos timestamp__gte en lugar de timestamp__date__gte
    access_logs = request.user.access_logs.filter(
        timestamp__gte=thirty_days_ago_start,
        status='allowed'
    ).order_by('-timestamp')
    
    # 2. Asistencias por semana (últimos 7 días)
    seven_days_ago = now_chile - timedelta(days=7)
    seven_days_ago_start = seven_days_ago.replace(hour=0, minute=0, second=0, microsecond=0)
    
    weekly_access = request.user.access_logs.filter(
        timestamp__gte=seven_days_ago_start,
        status='allowed'
    ).count()
    
    # 3. Asistencias del mes actual
    # Primer día del mes actual a las 00:00:00
    primer_dia_mes = now_chile.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    monthly_access = request.user.access_logs.filter(
        timestamp__gte=primer_dia_mes,
        status='allowed'
    ).count()
    
    # Asistencias totales
    total_access = request.user.access_logs.filter(status='allowed').count()
    
    # Calcular racha (días consecutivos)
    streak_days = calculate_streak(request.user)
    
    # 4. Acceso de hoy
    # Usamos un rango exacto del día para evitar problemas de conversión de DB
    start_of_day = now_chile.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now_chile.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    accessed_today = request.user.access_logs.filter(
        timestamp__range=(start_of_day, end_of_day),
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
    """Calcula la racha de días consecutivos de asistencia - CORREGIDO"""
    # Usamos lógica de rangos para evitar timestamp__date
    now_chile = timezone.localtime(timezone.now())
    current_date = now_chile
    streak = 0
    
    # Verificar los últimos 30 días
    for i in range(30):
        # Definir inicio y fin del día que estamos verificando
        start_of_day = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        has_access = AccessLog.objects.filter(
            user=user,
            timestamp__range=(start_of_day, end_of_day), # Uso de rango en lugar de __date
            status='allowed'
        ).exists()
        
        if has_access:
            streak += 1
            # Retroceder un día
            current_date -= timedelta(days=1)
        else:
            # Si hoy no vino, permitimos revisar si ayer vino para no romper la racha inmediatamente
            # (Opcional: Si quieres que la racha se rompa estrictamente si HOY no vino, quita este if)
            if i == 0: 
                current_date -= timedelta(days=1)
                continue
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