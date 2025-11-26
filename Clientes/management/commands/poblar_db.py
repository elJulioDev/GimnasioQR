import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from datetime import timedelta, datetime
from Clientes.models import CustomUser, Plan, Membership, AccessLog

# Configuración de Faker para español de Chile
fake = Faker(['es_CL'])

class Command(BaseCommand):
    help = 'Puebla la base de datos con usuarios históricos, planes y registros de prueba'

    def add_arguments(self, parser):
        parser.add_argument('total', type=int, help='Indica cuantos usuarios quieres crear')

    def handle(self, *args, **kwargs):
        total = kwargs['total']
        self.stdout.write(f'Creando {total} usuarios con historial de fechas...')

        # 1. Asegurar que existan los Planes correctos
        self.crear_planes_base()
        planes = list(Plan.objects.filter(is_active=True))

        for i in range(total):
            try:
                # --- A. Generar Fecha de Registro Aleatoria (Hace 3 años - Hoy) ---
                # Esto simula que la base de datos tiene antigüedad
                fecha_registro = fake.date_time_between(start_date='-3y', end_date='now', tzinfo=timezone.get_current_timezone())
                
                # 2. Crear Usuario
                rut = self.generar_rut_unico()
                first_name = fake.first_name()
                last_name = fake.last_name()
                username = f"{first_name.lower()}.{last_name.lower()}{random.randint(100,999)}"
                
                # Evitar duplicados
                if CustomUser.objects.filter(username=username).exists():
                    continue

                user = CustomUser.objects.create_user(
                    username=username,
                    email=f"{username}@example.com",
                    password='password123',
                    first_name=first_name,
                    last_name=last_name,
                    rut=rut,
                    phone=f"+569{random.randint(10000000, 99999999)}",
                    birthdate=fake.date_of_birth(minimum_age=18, maximum_age=65),
                    role='socio',
                    is_active=True,
                    # date_joined se sobreescribe abajo
                )

                # --- TRUCO DE VIAJE EN EL TIEMPO ---
                # Django auto_now_add ignora el valor en el create, así que lo actualizamos manualmente
                user.date_joined = fecha_registro
                user.created_at = fecha_registro
                user.save(update_fields=['date_joined', 'created_at'])
                
                # 3. Crear Membresía (80% de probabilidad)
                if random.random() < 0.8:
                    plan = random.choice(planes)
                    
                    # Determinar cuándo empezó la membresía:
                    # Puede ser una membresía vieja (ya vencida) o una nueva (activa)
                    # 70% probabilidad de que sea reciente (para que tengas datos en el dashboard actual)
                    if random.random() < 0.7:
                        dias_atras = random.randint(0, 30) # Reciente
                    else:
                        dias_atras = random.randint(31, 400) # Antigua/Vencida

                    start_date = timezone.now().date() - timedelta(days=dias_atras)
                    
                    # Validación: La membresía no puede empezar antes de que el usuario se registrara
                    if start_date < fecha_registro.date():
                        start_date = fecha_registro.date()

                    membership = Membership.objects.create(
                        user=user,
                        plan=plan,
                        start_date=start_date,
                        # end_date y status se calculan automáticamente en el save() del modelo
                        payment_method=random.choice(['efectivo', 'transferencia', 'tarjeta']),
                        amount_paid=plan.price,
                        notes="Carga masiva de datos"
                    )
                    
                    # Forzamos la fecha de pago para que coincida con el inicio
                    # (Membership tiene auto_now_add en payment_date a veces, o default=now)
                    membership.payment_date = timezone.datetime(
                        start_date.year, start_date.month, start_date.day, 
                        10, 0, 0, tzinfo=timezone.get_current_timezone()
                    )
                    membership.save()

                    # 4. Generar Historial de Accesos para esta membresía
                    self.generar_asistencias(user, membership)

                if (i + 1) % 10 == 0:
                    self.stdout.write(self.style.SUCCESS(f'Progreso: {i + 1}/{total} usuarios...'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error creando usuario {i}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'¡Éxito! Se han creado {total} usuarios con fechas históricas.'))

    def crear_planes_base(self):
        self.stdout.write('Sincronizando planes según archivo planes.txt...')
        
        # Usamos update_or_create para no duplicar si ya existen y actualizar si cambiaron
        
        # 1. Plan Estudiante (Mapeado al tipo 'diario' en tu modelo)
        Plan.objects.update_or_create(
            plan_type='diario',
            defaults={
                'name': "Plan Estudiante",
                'price': 18000,
                'duration_days': 30,
                'access_days': "Todos los días",
                'description': "Plan especial para estudiantes. Requiere credencial.",
                'includes_classes': True,
                'includes_nutritionist': False,
                'benefits': "Precio preferencial, Acceso diario, Clases básicas, Duchas",
                'is_active': True
            }
        )

        # 2. Plan Intermedio 4 Días (Mapeado al tipo 'finde' en tu modelo)
        Plan.objects.update_or_create(
            plan_type='finde',
            defaults={
                'name': "Plan Intermedio 4 Días",
                'price': 22000,
                'duration_days': 30,
                'access_days': "Lunes, Miércoles, Viernes, Sábado",
                'description': "Plan flexible de 4 días a la semana.",
                'includes_classes': True,
                'includes_nutritionist': False,
                'benefits': "Acceso máquinas, Clases incluidas, Casilleros diario",
                'is_active': True
            }
        )

        # 3. Plan Completo (Mapeado al tipo 'completo')
        Plan.objects.update_or_create(
            plan_type='completo',
            defaults={
                'name': "Plan Completo",
                'price': 25000,
                'duration_days': 30,
                'access_days': "Todos los días",
                'description': "Acceso ilimitado con todos los beneficios.",
                'includes_classes': True,
                'includes_nutritionist': True,
                'benefits': "Acceso ilimitado, Nutricionista, Evaluación física, Invitaciones amigos",
                'is_active': True
            }
        )

    def generar_rut_unico(self):
        """Genera un RUT válido y único"""
        while True:
            numero = random.randint(5000000, 28000000) # Rango amplio de RUTs
            dv = self.calcular_dv(numero)
            rut_completo = f"{numero}-{dv}"
            if not CustomUser.objects.filter(rut=rut_completo).exists():
                return rut_completo

    def calcular_dv(self, rut):
        aux = 1
        suma = 0
        for i in reversed(str(rut)):
            aux = (aux + 1) % 8 or 2
            suma += int(i) * aux
        resto = suma % 11
        return str(11 - resto) if resto > 1 else 'K' if resto == 1 else '0'

    def generar_asistencias(self, user, membership):
        """
        Genera logs de acceso desde el inicio de la membresía hasta su fin (o hasta hoy).
        Simula comportamiento real: a veces van, a veces no.
        """
        start = membership.start_date
        # El fin es lo que ocurra primero: vencimiento del plan o el día de hoy
        end = min(membership.end_date, timezone.now().date())
        
        # Si la membresía empieza en el futuro (raro pero posible), no generar asistencia
        if start > end:
            return

        delta = (end - start).days
        
        # Recorremos cada día de vigencia de la membresía
        for i in range(delta + 1):
            current_day = start + timedelta(days=i)
            
            # Probabilidad de ir al gym: 40%
            # Plus: La gente va menos los fines de semana
            probabilidad = 0.4
            if current_day.weekday() >= 5: # Sábado o Domingo
                probabilidad = 0.2

            if random.random() < probabilidad: 
                # Hora aleatoria realista (pic en la tarde y mañana)
                if random.random() < 0.3:
                    hora = random.randint(7, 10) # Mañana
                else:
                    hora = random.randint(17, 21) # Tarde
                
                minuto = random.randint(0, 59)
                
                fecha_hora_acceso = timezone.datetime(
                    current_day.year, current_day.month, current_day.day,
                    hora, minuto, tzinfo=timezone.get_current_timezone()
                )

                AccessLog.objects.create(
                    user=user,
                    timestamp=fecha_hora_acceso,
                    status='allowed',
                    membership=membership
                )