from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta, date, datetime
from django.db.models import Count, Sum, Q, Avg
import json
from .models import CustomUser, Plan, Membership, AccessLog
from .forms import CustomUserCreationForm
from .utils import send_qr_email
from django.db.models.functions import TruncMonth, TruncDay
from calendar import monthrange

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

# --- VISTAS DE PANELES (con proteccion de rol) ---

@login_required(login_url='inicio_sesion')
def index_admin(request):
    """Panel de administrador con estadisticas reales - solo para admins"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta area.')
        return redirect_by_role(request.user)
    
    # ==================== ESTADISTICAS DEL DASHBOARD ====================
    from django.db.models import Count, Sum, Q
    from datetime import date, timedelta
    
    # 1. Usuarios Activos (socios con membresia activa)
    usuarios_activos = CustomUser.objects.filter(role='socio', is_active_member=True).count()
    
    # Cambio porcentual (comparado con el mes anterior)
    today = timezone.now().date()
    primer_dia_mes = today.replace(day=1)
    anio_actual = today.year
    primer_dia_anio = date(anio_actual, 1, 1)
    mes_pasado = today - timedelta(days=30)
    usuarios_activos_mes_pasado = CustomUser.objects.filter(
        role='socio',
        is_active_member=True,
        created_at__lte=mes_pasado
    ).count()
    
    cambio_usuarios = calcular_porcentaje_cambio(usuarios_activos_mes_pasado, usuarios_activos)
    
    # 2. Ingresos Mensuales (suma de membresias del mes actual)
    primer_dia_mes = today.replace(day=1)
    ingresos_mensuales = Membership.objects.filter(
        payment_date__gte=primer_dia_mes,
        status__in=['active', 'pending']
    ).aggregate(total=Sum('amount_paid'))['total'] or 0

    # --- NUEVO: Ingresos Anuales (Year-to-Date) ---
    ingresos_anuales = Membership.objects.filter(
        payment_date__gte=primer_dia_anio,
        status__in=['active', 'pending']
    ).aggregate(total=Sum('amount_paid'))['total'] or 0

    # --- NUEVO: Ticket Promedio (ARPU - Average Revenue Per Unit de ventas) ---
    ticket_promedio = Membership.objects.filter(
        payment_date__year=anio_actual,
        status__in=['active', 'pending']
    ).aggregate(promedio=Avg('amount_paid'))['promedio'] or 0

    # Nuevo: Distribución por Método de Pago ---
    metodos_pago_data = Membership.objects.filter(
        payment_date__year=anio_actual,
        status__in=['active', 'pending']
    ).values('payment_method').annotate(
        total=Count('id'),
        dinero=Sum('amount_paid')
    ).order_by('-dinero')

    # Preparar datos para gráfico de Métodos de Pago
    labels_pago = [item['payment_method'].capitalize() for item in metodos_pago_data]
    data_pago = [float(item['dinero']) for item in metodos_pago_data]
    
    # Ingresos del mes anterior para comparacion
    mes_anterior_inicio = (primer_dia_mes - timedelta(days=1)).replace(day=1)
    mes_anterior_fin = primer_dia_mes - timedelta(days=1)
    ingresos_mes_anterior = Membership.objects.filter(
        payment_date__gte=mes_anterior_inicio,
        payment_date__lte=mes_anterior_fin,
        status__in=['active', 'pending']
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    cambio_ingresos = calcular_porcentaje_cambio(ingresos_mes_anterior, ingresos_mensuales)
    
    # 3. Planes por Vencer (proximos 7 dias)
    fecha_limite = today + timedelta(days=7)
    planes_por_vencer = Membership.objects.filter(
        is_active=True,
        end_date__gte=today,
        end_date__lte=fecha_limite
    ).count()
    
    # Comparacion con la semana anterior
    semana_pasada_inicio = today - timedelta(days=7)
    semana_pasada_fin = today
    planes_venciendo_semana_pasada = Membership.objects.filter(
        is_active=True,
        end_date__gte=semana_pasada_inicio,
        end_date__lte=semana_pasada_fin
    ).count()
    
    cambio_planes = calcular_porcentaje_cambio(planes_venciendo_semana_pasada, planes_por_vencer)
    
    # 4. Accesos Hoy
    from django.db.models.functions import TruncDate
    accesos_hoy = AccessLog.objects.filter(
        timestamp__date=today,
        status='allowed'
    ).count()
    
    # Comparacion con ayer
    ayer = today - timedelta(days=1)
    accesos_ayer = AccessLog.objects.filter(
        timestamp__date=ayer,
        status='allowed'
    ).count()
    
    cambio_accesos = calcular_porcentaje_cambio(accesos_ayer, accesos_hoy)
    
    # ==================== GESTION DE USUARIOS ====================
    
    # Obtener SOCIOS (excluyendo admins y moderadores)
    socios = CustomUser.objects.filter(
        role='socio',
        is_superuser=False
    ).select_related().prefetch_related('memberships').order_by('-created_at')
    
    # Enriquecer cada socio con su membresia activa
    socios_data = []
    for socio in socios:
        membership = socio.get_active_membership()
        socios_data.append({
            'user': socio,
            'membership': membership,
            'plan_name': membership.plan.name if membership else 'Sin plan',
            'estado': 'Activo' if socio.is_active_member else 'Inactivo',
            'dias_restantes': membership.days_remaining() if membership else 0
        })
    
    # Obtener MODERADORES
    moderadores = CustomUser.objects.filter(
        role='moderador',
        is_superuser=False
    ).order_by('-created_at')

    # --- AGREGAR ESTO: Obtener ADMINISTRADORES ---
    administradores = CustomUser.objects.filter(
        role='admin',
        is_superuser=False # Excluímos al superuser de Django si lo deseas, o quítalo para ver todos
    ).order_by('-created_at')

    # Estadisticas adicionales de usuarios
    total_socios = socios.count()
    total_moderadores = moderadores.count()
    total_admins = administradores.count() # <--- AGREGAR ESTO
    
    # Estadisticas adicionales de usuarios
    total_socios = socios.count()
    total_moderadores = moderadores.count()
    socios_activos = socios.filter(is_active_member=True).count()
    socios_inactivos = socios.filter(is_active_member=False).count()
    
    # ==================== GESTION DE PLANES ====================
    
    planes = Plan.objects.filter(is_active=True).annotate(
        usuarios_inscritos=Count(
            'memberships',
            filter=Q(memberships__is_active=True)
        )
    ).order_by('price')

    planes = Plan.objects.filter(is_active=True).annotate(
        usuarios_inscritos=Count('memberships', filter=Q(memberships__is_active=True))
    ).order_by('price')

    # En la seccion de planes, reemplaza:
    planes_data = []
    total_ingresos_historico_planes = 0

    # Primero calculamos totales para porcentajes
    total_revenue_all = Membership.objects.filter(status__in=['active', 'pending']).aggregate(t=Sum('amount_paid'))['t'] or 1

    for plan in planes:
        ingresos_plan = Membership.objects.filter(
            plan=plan,
            payment_date__gte=primer_dia_mes,
            status__in=['active', 'pending']
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
        
        ingresos_historicos_plan = Membership.objects.filter(
            plan=plan,
            status__in=['active', 'pending']
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

        # Porcentaje de contribución a las ganancias totales
        share_ganancias = (ingresos_historicos_plan / total_revenue_all) * 100 if total_revenue_all > 0 else 0

        planes_data.append({
            'plan': plan,
            'usuarios_inscritos': plan.usuarios_inscritos,
            'ingresos_mes': ingresos_plan,
            'ingresos_total': ingresos_historicos_plan, # Nuevo
            'share': round(share_ganancias, 1) # Nuevo
        })


    # ==================== DATOS PARA GRAFICOS ====================
    
    # 1. Gráfico de Ingresos (Últimos 6 meses)
    ingresos_chart_labels = []
    ingresos_chart_data = []
    
    for i in range(5, -1, -1):
        fecha_mes = today.replace(day=1) - timedelta(days=i*30) # Aprox
        mes_inicio = fecha_mes.replace(day=1)
        # Truco para obtener el fin de mes
        siguiente_mes = mes_inicio + timedelta(days=32)
        mes_fin = siguiente_mes.replace(day=1) - timedelta(days=1)
        
        total_mes = Membership.objects.filter(
            payment_date__gte=mes_inicio,
            payment_date__lte=mes_fin,
            status__in=['active', 'pending']
        ).aggregate(total=Sum('amount_paid'))['total'] or 0
        
        # Nombres de meses en español
        meses_es = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        nombre_mes = meses_es[mes_inicio.month - 1]
        
        ingresos_chart_labels.append(nombre_mes)
        ingresos_chart_data.append(float(total_mes))

    # 2. Gráfico de Distribución de Planes
    planes_dist = Membership.objects.filter(is_active=True).values('plan__name').annotate(total=Count('id'))
    planes_labels = [p['plan__name'] for p in planes_dist]
    chart_planes_data_values = [p['total'] for p in planes_dist]

    # 3. Gráfico de Asistencias (Últimos 7 días)
    asistencias_labels = []
    asistencias_data = []
    
    for i in range(6, -1, -1):
        fecha = today - timedelta(days=i)
        cnt = AccessLog.objects.filter(
            timestamp__date=fecha,
            status='allowed'
        ).count()
        asistencias_labels.append(fecha.strftime("%d/%m"))
        asistencias_data.append(cnt)

    # ==================== NUEVO: GESTIÓN DE ASISTENCIAS ====================
    
    # 1. Obtener todos los logs de HOY
    logs_hoy = AccessLog.objects.filter(
        timestamp__date=today
    ).select_related('user', 'membership', 'membership__plan').order_by('-timestamp')

    # 2. Calcular Ausentes (Usuarios con membresía activa que NO están en los logs de hoy)
    # Obtenemos IDs únicos de quienes asistieron hoy (solo accesos permitidos)
    ids_asistentes_hoy = AccessLog.objects.filter(
        timestamp__date=today,
        status='allowed'
    ).values_list('user_id', flat=True)

    # Filtramos socios activos excluyendo a los que vinieron
    socios_ausentes = CustomUser.objects.filter(
        role='socio',
        is_active_member=True
    ).exclude(
        id__in=ids_asistentes_hoy
    ).select_related().order_by('last_name')

    # Enriquecer datos de ausentes con su plan
    ausentes_data = []
    for socio in socios_ausentes:
        membresia = socio.get_active_membership()
        if membresia:
            ausentes_data.append({
                'user': socio,
                'plan': membresia.plan.name,
                'dias_restantes': membresia.days_remaining()
            })


    # ==================== CONTEXTO PARA EL TEMPLATE ====================
    
    context = {
        # Estadisticas Dashboard
        'usuarios_activos': usuarios_activos,
        'cambio_usuarios': cambio_usuarios,
        'ingresos_mensuales': ingresos_mensuales,
        'cambio_ingresos': cambio_ingresos,
        'planes_por_vencer': planes_por_vencer,
        'cambio_planes': cambio_planes,
        'accesos_hoy': accesos_hoy,
        'cambio_accesos': cambio_accesos,

        'ingresos_anuales': ingresos_anuales,
        'ticket_promedio': ticket_promedio,
        'chart_pagos_labels': json.dumps(labels_pago),
        'chart_pagos_data': json.dumps(data_pago),
        
        # Gestion de Usuarios
        'socios': socios_data,
        'moderadores': moderadores,
        'administradores': administradores,
        'total_socios': total_socios,
        'total_moderadores': total_moderadores,
        'socios_activos': socios_activos,
        'socios_inactivos': socios_inactivos,
        'total_admins': total_admins,
        
        # Gestion de Planes
        'lista_planes': planes_data,
        'total_planes': planes.count(),

        # NUEVAS VARIABLES PARA GRÁFICOS (Serializadas para JS)
        'chart_ingresos_labels': json.dumps(ingresos_chart_labels),
        'chart_ingresos_data': json.dumps(ingresos_chart_data),
        'chart_planes_labels': json.dumps(planes_labels),
        'chart_planes_data': json.dumps(chart_planes_data_values),
        'chart_asistencias_labels': json.dumps(asistencias_labels),
        'chart_asistencias_data': json.dumps(asistencias_data),

        # --- NUEVAS VARIABLES DE ASISTENCIA ---
        'logs_hoy': logs_hoy,
        'lista_ausentes': ausentes_data,
        'total_ausentes': len(ausentes_data),
        'porcentaje_asistencia': round((accesos_hoy / socios_activos * 100), 1) if socios_activos > 0 else 0

    }
    
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
            
            user.is_active = request.POST.get('is_active') == 'on'
            
            # 2. Gestión de Membresía
            if user.role == 'socio':
                user.is_active_member = request.POST.get('is_active_member') == 'on'
                
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
                                if end_date_obj >= timezone.now().date():
                                    current_membership.status = 'active'
                                    current_membership.is_active = True
                                else:
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


# ==================== GESTION DE PLANES (ADMIN) ====================

@login_required(login_url='inicio_sesion')
def admin_plan_create(request):
    """Crear nuevo plan - Solo admin"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta area.')
        return redirect('index_admin')
    
    if request.method == 'GET':
        # Mostrar formulario de creacion
        context = {
            'is_admin_creation': True
        }
        return render(request, 'admin_plan_create.html', context)
    
    elif request.method == 'POST':
        return process_admin_plan_creation(request)

def process_admin_plan_creation(request):
    """Procesa la creacion de plan por el admin"""
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
        required_fields = ['name', 'plan_type', 'description', 'price', 'duration_days', 'access_days']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return JsonResponse({
                'success': False,
                'error': f'Campos requeridos faltantes: {", ".join(missing_fields)}'
            }, status=400)
        
        # CAMBIO: ELIMINADA la validación que impedía duplicar plan_type
        # (Permitimos múltiples planes del mismo tipo, ej: Premium Mensual y Premium Anual)
        
        # Crear el plan
        plan = Plan.objects.create(
            name=data['name'],
            plan_type=data['plan_type'],
            description=data['description'],
            price=data['price'],
            duration_days=data['duration_days'],
            access_days=data['access_days'],
            includes_classes=data.get('includes_classes', False) == 'true' or data.get('includes_classes') == True,
            includes_nutritionist=data.get('includes_nutritionist', False) == 'true' or data.get('includes_nutritionist') == True,
            benefits=data.get('benefits', ''),
            is_active=True
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Plan {plan.name} creado correctamente',
            'plan_id': plan.id
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error al crear plan: {str(e)}'
        }, status=500)

@login_required(login_url='inicio_sesion')
def admin_plan_details(request, plan_id):
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No autorizado')
        return redirect('index_admin')
    
    try:
        plan = Plan.objects.get(id=plan_id)
        
        # 1. Usuarios Activos (Lista para la tabla)
        active_memberships = Membership.objects.filter(
            plan=plan, is_active=True
        ).select_related('user').order_by('end_date')

        # 2. Métricas Generales (KPIs)
        kpi_active_users = active_memberships.count()
        kpi_total_sold = Membership.objects.filter(plan=plan).count()
        
        # Ingresos Totales Históricos
        kpi_total_revenue = Membership.objects.filter(
            plan=plan, status__in=['active', 'pending']
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

        # Ingresos Este Mes
        first_day_month = timezone.now().date().replace(day=1)
        kpi_monthly_revenue = Membership.objects.filter(
            plan=plan, 
            payment_date__gte=first_day_month,
            status__in=['active', 'pending']
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

        # 3. Datos para el Gráfico (Últimos 6 meses)
        # Esto agrupa las ventas de este plan por mes
        six_months_ago = timezone.now().date() - timedelta(days=180)
        chart_data_query = Membership.objects.filter(
            plan=plan,
            payment_date__gte=six_months_ago,
            status__in=['active', 'pending']
        ).annotate(month=TruncMonth('payment_date')).values('month').annotate(
            total=Sum('amount_paid'),
            count=Count('id')
        ).order_by('month')

        # Formatear para Chart.js
        chart_labels = []
        chart_values = []
        for entry in chart_data_query:
            if entry['month']:
                chart_labels.append(entry['month'].strftime("%b %Y")) # Ej: "Nov 2025"
                chart_values.append(int(entry['total'])) # Ej: 50000

        # 4. Beneficios como lista
        beneficios_lista = [b.strip() for b in plan.benefits.split(',')] if plan.benefits else []

        context = {
            'plan': plan,
            'active_memberships': active_memberships,
            
            # KPIs
            'kpi_active': kpi_active_users,
            'kpi_total_sold': kpi_total_sold,
            'kpi_total_rev': kpi_total_revenue,
            'kpi_monthly_rev': kpi_monthly_revenue,
            
            # Chart Data
            'chart_labels': json.dumps(chart_labels),
            'chart_values': json.dumps(chart_values),
            
            'beneficios_lista': beneficios_lista
        }
        
        return render(request, 'admin_plan_details.html', context)

    except Plan.DoesNotExist:
        messages.error(request, 'Plan no encontrado')
        return redirect('index_admin')

@login_required(login_url='inicio_sesion')
def admin_plan_edit(request, plan_id):
    """Editar plan - Solo admin"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta area.')
        return redirect('index_admin')
    
    try:
        plan = Plan.objects.get(id=plan_id)
        
        if request.method == 'GET':
            # PASAR EL OBJETO 'plan' AL CONTEXTO CON EL NOMBRE CORRECTO
            context = {
                'plan': plan,  # Nombre correcto que usa el template
            }
            return render(request, 'admin_plan_edit.html', context)
        
        elif request.method == 'POST':
            # Manejar tanto JSON como POST
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            # Actualizar campos
            plan.name = data.get('name', plan.name)
            plan.description = data.get('description', plan.description)
            plan.price = data.get('price', plan.price)
            plan.duration_days = data.get('duration_days', plan.duration_days)
            plan.access_days = data.get('access_days', plan.access_days)
            plan.includes_classes = data.get('includes_classes', 'False') == 'true' or data.get('includes_classes') == True
            plan.includes_nutritionist = data.get('includes_nutritionist', 'False') == 'true' or data.get('includes_nutritionist') == True
            plan.benefits = data.get('benefits', plan.benefits)
            plan.is_active = data.get('is_active', 'True') == 'true' or data.get('is_active') == True
            
            plan.save()
            
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': True,
                    'message': f'Plan {plan.name} actualizado correctamente'
                })
            else:
                messages.success(request, f'Plan {plan.name} actualizado correctamente')
                return redirect('admin_plan_details', plan_id=plan.id)
                
    except Plan.DoesNotExist:
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': False,
                'error': 'Plan no encontrado'
            }, status=404)
        else:
            messages.error(request, 'Plan no encontrado')
            return redirect('index_admin')


@login_required(login_url='inicio_sesion')
def admin_plan_delete(request, plan_id):
    """Eliminar plan - Solo admin"""
    if not request.user.role or request.user.role != 'admin':
        messages.error(request, 'No tienes permisos para acceder a esta area.')
        return redirect('index_admin')
    
    try:
        plan = Plan.objects.get(id=plan_id)
        
        if request.method == 'POST':
            # Verificar si tiene membresias activas
            active_memberships = Membership.objects.filter(plan=plan, is_active=True).count()
            
            if active_memberships > 0:
                messages.error(request, f'No se puede eliminar el plan porque tiene {active_memberships} membresias activas.')
                return redirect('admin_plan_details', plan_id=plan.id)
            
            # Confirmar eliminacion
            plan_name = plan.name
            plan.delete()
            
            messages.success(request, f'Plan {plan_name} eliminado correctamente')
            return redirect('index_admin')
        
    except Plan.DoesNotExist:
        messages.error(request, 'Plan no encontrado')
        return redirect('index_admin')

@require_http_methods(["POST"])
def process_qr_scan(request):
    """
    Procesa el escaneo de QR y registra el acceso del usuario.
    Valida la membresía y guarda en AccessLog.
    SOLO PERMITE UN REGISTRO POR DÍA por usuario.
    """
    try:
        # Obtener datos del QR
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
        
        qr_data = data.get('qr_data')
        
        # LOG para debugging
        print(f"[DEBUG] QR Data recibido: {qr_data}")
        print(f"[DEBUG] Tipo de qr_data: {type(qr_data)}")
        
        if not qr_data:
            return JsonResponse({
                'success': False,
                'error': 'No se proporcionó información del QR'
            }, status=400)
        
        # Parsear datos del QR con múltiples intentos
        user_id = None
        qr_id = None
        rut = None
        
        try:
            # Intento 1: Si es un string que parece un diccionario Python
            if isinstance(qr_data, str):
                # Limpiar el string
                qr_data_clean = qr_data.strip()
                
                print(f"[DEBUG] QR Data limpio: {qr_data_clean}")
                
                # Intentar parsear como diccionario de Python
                import ast
                qr_dict = ast.literal_eval(qr_data_clean)
                
                print(f"[DEBUG] QR Dict parseado: {qr_dict}")
                
                user_id = qr_dict.get('user_id')
                qr_id = qr_dict.get('qr_id')
                rut = qr_dict.get('rut')
            
            # Intento 2: Si ya es un diccionario
            elif isinstance(qr_data, dict):
                user_id = qr_data.get('user_id')
                qr_id = qr_data.get('qr_id')
                rut = qr_data.get('rut')
            
            else:
                # Intento 3: Intentar como JSON
                try:
                    qr_dict = json.loads(qr_data)
                    user_id = qr_dict.get('user_id')
                    qr_id = qr_dict.get('qr_id')
                    rut = qr_dict.get('rut')
                except:
                    pass
            
            print(f"[DEBUG] Datos extraídos - user_id: {user_id}, qr_id: {qr_id}, rut: {rut}")
            
            # Validar que se extrajeron los datos
            if not user_id or not qr_id or not rut:
                return JsonResponse({
                    'success': False,
                    'error': f'Formato de QR inválido. Datos recibidos: {qr_data[:100]}'
                }, status=400)
                
        except Exception as parse_error:
            print(f"[DEBUG ERROR] Error al parsear QR: {str(parse_error)}")
            return JsonResponse({
                'success': False,
                'error': f'Error al parsear QR: {str(parse_error)}. Formato recibido: {str(qr_data)[:100]}'
            }, status=400)
        
        # Buscar usuario
        try:
            user = CustomUser.objects.get(id=user_id, rut=rut, qr_unique_id=qr_id)
            print(f"[DEBUG] Usuario encontrado: {user.get_full_name()}")
        except CustomUser.DoesNotExist:
            print(f"[DEBUG ERROR] Usuario no encontrado con: id={user_id}, rut={rut}, qr_id={qr_id}")
            return JsonResponse({
                'success': False,
                'status': 'denied',
                'error': 'Usuario no encontrado o QR inválido',
                'user': {
                    'name': 'Desconocido',
                    'rut': rut or 'N/A'
                }
            }, status=404)
        
        # Verificar membresía activa
        membership = user.get_active_membership()
        print(f"[DEBUG] Membresía activa: {membership}")
        
        if not membership or not membership.is_valid():
            # Registrar acceso DENEGADO
            AccessLog.objects.create(
                user=user,
                status='denied',
                membership=membership,
                denial_reason='Membresía vencida o inexistente'
            )
            
            print(f"[DEBUG] Acceso DENEGADO para {user.get_full_name()} - Membresía vencida")
            
            return JsonResponse({
                'success': False,
                'status': 'denied',
                'error': 'Membresía vencida o inexistente',
                'user': {
                    'name': user.get_full_name(),
                    'rut': user.rut,
                    'membership_status': 'Vencida' if membership else 'Sin membresía'
                }
            })
        
        # ✅ VERIFICAR SI YA INGRESÓ HOY - BLOQUEAR SI EXISTE REGISTRO
        today = timezone.now().date()
        already_accessed_today = AccessLog.objects.filter(
            user=user,
            timestamp__date=today,
            status='allowed'
        ).exists()
        
        # ✅ SI YA INGRESÓ HOY, DENEGAR Y NO CREAR NUEVO REGISTRO
        if already_accessed_today:
            # Obtener el registro de hoy para mostrar la hora
            todays_access = AccessLog.objects.filter(
                user=user,
                timestamp__date=today,
                status='allowed'
            ).first()
            
            print(f"[DEBUG] ⚠️  Usuario {user.get_full_name()} YA INGRESÓ HOY a las {todays_access.timestamp.strftime('%H:%M:%S')}")
            
            # Calcular asistencias para mostrar en la respuesta
            primer_dia_mes = today.replace(day=1)
            monthly_access = AccessLog.objects.filter(
                user=user,
                timestamp__date__gte=primer_dia_mes,
                status='allowed'
            ).count()
            
            seven_days_ago = today - timedelta(days=7)
            weekly_access = AccessLog.objects.filter(
                user=user,
                timestamp__date__gte=seven_days_ago,
                status='allowed'
            ).count()
            
            return JsonResponse({
                'success': False,
                'status': 'denied',
                'error': f'Ya registraste tu entrada hoy a las {todays_access.timestamp.strftime("%H:%M:%S")}',
                'already_accessed_today': True,
                'user': {
                    'name': user.get_full_name(),
                    'rut': user.rut,
                    'email': user.email,
                    'membership_plan': membership.plan.name,
                    'membership_end': membership.end_date.isoformat(),
                    'days_remaining': membership.days_remaining(),
                    'monthly_access': monthly_access,
                    'weekly_access': weekly_access,
                    'access_time': todays_access.timestamp.strftime('%H:%M:%S'),
                    'first_access_today': todays_access.timestamp.strftime('%H:%M:%S')
                }
            }, status=403)  # 403 Forbidden - Ya ingresó hoy
        
        # ✅ SI NO HA INGRESADO HOY, CREAR REGISTRO DE ACCESO
        access_log = AccessLog.objects.create(
            user=user,
            status='allowed',
            membership=membership
        )
        
        print(f"[DEBUG] ✅ Acceso PERMITIDO para {user.get_full_name()} - ID Log: {access_log.id}")
        print(f"[DEBUG] ✅ Primera entrada del día registrada exitosamente")
        
        # Calcular asistencias del mes actual
        primer_dia_mes = today.replace(day=1)
        monthly_access = AccessLog.objects.filter(
            user=user,
            timestamp__date__gte=primer_dia_mes,
            status='allowed'
        ).count()
        
        # Calcular asistencias semanales
        seven_days_ago = today - timedelta(days=7)
        weekly_access = AccessLog.objects.filter(
            user=user,
            timestamp__date__gte=seven_days_ago,
            status='allowed'
        ).count()
        
        print(f"[DEBUG] Asistencias - Semanal: {weekly_access}, Mensual: {monthly_access}")
        
        return JsonResponse({
            'success': True,
            'status': 'allowed',
            'message': '¡Acceso permitido! Bienvenido al gimnasio',
            'already_accessed_today': False,
            'user': {
                'id': user.id,
                'name': user.get_full_name(),
                'rut': user.rut,
                'email': user.email,
                'membership_plan': membership.plan.name,
                'membership_end': membership.end_date.isoformat(),
                'days_remaining': membership.days_remaining(),
                'monthly_access': monthly_access,
                'weekly_access': weekly_access,
                'access_time': access_log.timestamp.strftime('%H:%M:%S')
            }
        })
        
    except Exception as e:
        print(f"[DEBUG ERROR GENERAL] {str(e)}")
        import traceback
        traceback.print_exc()
        
        return JsonResponse({
            'success': False,
            'error': f'Error al procesar QR: {str(e)}'
        }, status=500)

def mostrar_Scanner(request):
    """Esta vista renderiza la pagina del Scanner."""
    return render(request, 'QR_Scanner.html')


def mostrar_QRCodeEmail(request):
    """Esta vista renderiza la pagina email."""
    return render(request, 'qr_code_email.html')


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

@require_http_methods(["POST"])
@login_required(login_url='inicio_sesion')
def api_renovar_plan(request):
    """API para procesar la renovación, calculando fechas y guardando notas"""
    try:
        data = json.loads(request.body)
        rut = data.get('rut')
        plan_id = data.get('plan_id')
        payment_method = data.get('payment_method')
        notes = data.get('notes', '') # Capturamos las notas del formulario

        # 1. Obtener Usuario y Plan
        user = CustomUser.objects.get(rut=rut)
        plan = Plan.objects.get(id=plan_id)

        # 2. Calcular fechas inteligentes
        today = timezone.now().date()
        
        # Verificar si tiene una membresía que vence en el futuro para extenderla
        current_membership = Membership.objects.filter(
            user=user, 
            is_active=True, 
            end_date__gte=today
        ).order_by('-end_date').first()
        
        if current_membership:
            # Si tiene plan activo, el nuevo empieza el día después de que termine el actual
            start_date = current_membership.end_date + timedelta(days=1)
            # Opcional: Desactivamos la anterior para que solo haya una "primary"
            # current_membership.is_active = False 
            # current_membership.save()
        else:
            # Si no tiene plan o está vencido, empieza hoy
            start_date = today

        # Calcular fecha de fin basada en la duración del plan
        end_date = start_date + timedelta(days=plan.duration_days)

        # 3. Crear Nueva Membresía
        Membership.objects.create(
            user=user,
            plan=plan,
            start_date=start_date,
            end_date=end_date, # Guardamos la fecha calculada
            payment_method=payment_method,
            amount_paid=plan.price,
            status='active',
            is_active=True,
            notes=f"Renovación: {notes} - Atendido por {request.user.get_full_name()}"
        )

        # 4. Actualizar estado del usuario
        user.is_active_member = True
        user.save()

        return JsonResponse({'success': True, 'message': 'Plan renovado correctamente'})

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