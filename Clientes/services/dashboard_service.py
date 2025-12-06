import json
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
from datetime import timedelta, date
from ..models import CustomUser, Plan, Membership, AccessLog, Payment

class AdminDashboardService:
    def __init__(self):
        # Fechas base para cálculos
        self.today = timezone.now().date()
        self.now_chile = timezone.localtime(timezone.now())
        self.start_of_day = self.now_chile.replace(hour=0, minute=0, second=0, microsecond=0)
        self.end_of_day = self.now_chile.replace(hour=23, minute=59, second=59, microsecond=999999)

    def _calculate_percentage_change(self, old_value, new_value):
        """Método privado para calcular variaciones porcentuales."""
        if old_value == 0:
            return {'porcentaje': 100, 'es_positivo': True} if new_value > 0 else {'porcentaje': 0, 'es_positivo': True}
        
        change = ((new_value - old_value) / old_value) * 100
        return {
            'porcentaje': abs(round(change, 1)),
            'es_positivo': change >= 0
        }

    def get_kpis(self):
        """Obtiene los indicadores clave de rendimiento (KPIs)."""
        # 1. Usuarios Activos
        active_users = CustomUser.objects.filter(role='socio', is_active_member=True).count()
        last_month = self.today - timedelta(days=30)
        active_users_last = CustomUser.objects.filter(role='socio', is_active_member=True, created_at__lte=last_month).count()
        user_change = self._calculate_percentage_change(active_users_last, active_users)

        # 2. Ingresos Mensuales
        first_day_month = self.today.replace(day=1)
        monthly_revenue = Membership.objects.filter(payment_date__gte=first_day_month).exclude(status='cancelled').aggregate(t=Sum('amount_paid'))['t'] or 0
        
        prev_month_start = (first_day_month - timedelta(days=1)).replace(day=1)
        prev_month_end = first_day_month - timedelta(days=1)
        prev_revenue = Membership.objects.filter(payment_date__gte=prev_month_start, payment_date__lte=prev_month_end).exclude(status='cancelled').aggregate(t=Sum('amount_paid'))['t'] or 0
        revenue_change = self._calculate_percentage_change(prev_revenue, monthly_revenue)

        # 3. Planes por Vencer (7 días)
        limit_date = self.today + timedelta(days=7)
        plans_expiring = Membership.objects.filter(is_active=True, end_date__gte=self.today, end_date__lte=limit_date).count()
        
        week_start = self.today - timedelta(days=7)
        plans_expiring_last = Membership.objects.filter(is_active=True, end_date__gte=week_start, end_date__lte=self.today).count()
        plans_change = self._calculate_percentage_change(plans_expiring_last, plans_expiring)

        # 4. Accesos Hoy
        accesses_today = AccessLog.objects.filter(timestamp__range=(self.start_of_day, self.end_of_day), status='allowed').count()
        yesterday_start = self.start_of_day - timedelta(days=1)
        yesterday_end = self.end_of_day - timedelta(days=1)
        accesses_yesterday = AccessLog.objects.filter(timestamp__range=(yesterday_start, yesterday_end), status='allowed').count()
        access_change = self._calculate_percentage_change(accesses_yesterday, accesses_today)

        # Extras financieros
        year_start = date(self.today.year, 1, 1)

        annual_revenue = Payment.objects.filter(
            date__gte=year_start
        ).aggregate(t=Sum('amount'))['t'] or 0

        avg_ticket = Payment.objects.filter(
            date__year=self.today.year
        ).aggregate(a=Avg('amount'))['a'] or 0

        return {
            'usuarios_activos': active_users, 'cambio_usuarios': user_change,
            'ingresos_mensuales': monthly_revenue, 'cambio_ingresos': revenue_change,
            'planes_por_vencer': plans_expiring, 'cambio_planes': plans_change,
            'accesos_hoy': accesses_today, 'cambio_accesos': access_change,
            'ingresos_anuales': annual_revenue, 'ticket_promedio': avg_ticket
        }

    def get_user_stats(self):
        """Prepara las listas de usuarios y estadísticas de roles."""
        # Socios (Optimizando consulta N+1)
        socios = CustomUser.objects.filter(role='socio', is_superuser=False).select_related().prefetch_related('memberships').order_by('-created_at')
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
        
        moderadores = CustomUser.objects.filter(role='moderador', is_superuser=False).order_by('-created_at')
        administradores = CustomUser.objects.filter(role='admin', is_superuser=False).order_by('-created_at')

        return {
            'socios': socios_data,
            'moderadores': moderadores,
            'administradores': administradores,
            'total_socios': socios.count(),
            'total_moderadores': moderadores.count(),
            'total_admins': administradores.count(),
            'socios_activos': socios.filter(is_active_member=True).count(),
            'socios_inactivos': socios.filter(is_active_member=False).count()
        }

    def get_plan_stats(self):
        """Calcula estadísticas por plan y participación en ingresos."""
        planes = Plan.objects.filter(is_active=True).annotate(
            usuarios_inscritos=Count('memberships', filter=Q(memberships__is_active=True))
        ).order_by('price')
        
        total_revenue = Membership.objects.filter(status__in=['active', 'pending']).aggregate(t=Sum('amount_paid'))['t'] or 1
        first_day_month = self.today.replace(day=1)
        
        planes_data = []
        for plan in planes:
            ingresos_mes = Membership.objects.filter(plan=plan, payment_date__gte=first_day_month, status__in=['active', 'pending']).aggregate(t=Sum('amount_paid'))['t'] or 0
            ingresos_total = Membership.objects.filter(plan=plan, status__in=['active', 'pending']).aggregate(t=Sum('amount_paid'))['t'] or 0
            share = (ingresos_total / total_revenue) * 100 if total_revenue > 0 else 0
            
            planes_data.append({
                'plan': plan,
                'usuarios_inscritos': plan.usuarios_inscritos,
                'ingresos_mes': ingresos_mes,
                'ingresos_total': ingresos_total,
                'share': round(share, 1)
            })
        
        return {'lista_planes': planes_data, 'total_planes': planes.count()}

    def get_charts_data(self):
        """Prepara los datos JSON para Chart.js."""
        # Métodos de Pago
        methods = Payment.objects.filter(
            date__year=self.today.year
        ).values('payment_method').annotate(
            total=Count('id'), 
            dinero=Sum('amount')
        ).order_by('-dinero')

        labels_pago = [m['payment_method'].capitalize() for m in methods]
        data_pago = [float(m['dinero']) for m in methods]

        # Ingresos Mensuales
        labels_ingresos = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        data_ingresos = [0] * 12
        pagos = Payment.objects.filter(date__year=self.today.year)
        for pago in pagos:
            mes = pago.date.month - 1
            data_ingresos[mes] += float(pago.amount)
        
        # Distribución Planes
        planes_dist = Membership.objects.filter(is_active=True).values('plan__name').annotate(total=Count('id'))
        labels_planes = [p['plan__name'] for p in planes_dist]
        data_planes = [p['total'] for p in planes_dist]

        # Asistencia (7 días)
        labels_asist = []
        data_asist = []
        for i in range(6, -1, -1):
            d = self.today - timedelta(days=i)
            cnt = AccessLog.objects.filter(timestamp__date=d, status='allowed').count()
            labels_asist.append(d.strftime("%d/%m"))
            data_asist.append(cnt)

        current_month = self.today.month
        return {
            'chart_pagos_labels': json.dumps(labels_pago),
            'chart_pagos_data': json.dumps(data_pago),
            'chart_ingresos_labels': json.dumps(labels_ingresos[:current_month]),
            'chart_ingresos_data': json.dumps(data_ingresos[:current_month]),
            'chart_planes_labels': json.dumps(labels_planes),
            'chart_planes_data': json.dumps(data_planes),
            'chart_asistencias_labels': json.dumps(labels_asist),
            'chart_asistencias_data': json.dumps(data_asist)
        }

    def get_attendance_details(self):
        """Obtiene logs del día y usuarios ausentes."""
        logs_hoy = AccessLog.objects.filter(timestamp__range=(self.start_of_day, self.end_of_day)).select_related('user', 'membership', 'membership__plan').order_by('-timestamp')
        
        ids_presentes = AccessLog.objects.filter(timestamp__date=self.today, status='allowed').values_list('user_id', flat=True)
        socios_ausentes = CustomUser.objects.filter(role='socio', is_active_member=True).exclude(id__in=ids_presentes).select_related().order_by('last_name')
        
        ausentes_data = []
        for socio in socios_ausentes:
            membresia = socio.get_active_membership()
            if membresia:
                ausentes_data.append({
                    'user': socio, 'plan': membresia.plan.name, 'dias_restantes': membresia.days_remaining()
                })
        
        socios_activos = CustomUser.objects.filter(role='socio', is_active_member=True).count()
        accesos_hoy = AccessLog.objects.filter(timestamp__range=(self.start_of_day, self.end_of_day), status='allowed').count()
        asistencia_pct = round((accesos_hoy / socios_activos * 100), 1) if socios_activos > 0 else 0

        return {
            'logs_hoy': logs_hoy,
            'lista_ausentes': ausentes_data,
            'total_ausentes': len(ausentes_data),
            'porcentaje_asistencia': asistencia_pct
        }

    def get_transactions(self):
        """Historial de transacciones (Desde Payment)."""
        # Ahora mostramos Payment, que nunca se borra
        transacciones = Payment.objects.all().order_by('-date')
        total_historico = Payment.objects.aggregate(t=Sum('amount'))['t'] or 0
        
        return {'transacciones': transacciones, 'total_historico': total_historico}