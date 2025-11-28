import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from datetime import timedelta
from Clientes.models import CustomUser, Plan, Membership, AccessLog

# Configuración de Faker para español de Chile
fake = Faker(['es_CL'])

class Command(BaseCommand):
    help = 'Puebla la base de datos con usuarios históricos, planes y registros de prueba'

    def add_arguments(self, parser):
        parser.add_argument('total', type=int, help='Indica cuantos usuarios quieres crear')

    def handle(self, *args, **kwargs):
        total = kwargs['total']
        self.stdout.write(f'Creando {total} registros históricos distribuidos en 6 meses...')

        # 1. Asegurar planes
        self.crear_planes_base()
        planes = list(Plan.objects.filter(is_active=True))

        # Calculamos cuántos días han pasado desde el 1 de Enero de este año
        now = timezone.now()
        inicio_anio = now.replace(month=1, day=1, hour=0, minute=0, second=0)
        dias_totales_anio = (now - inicio_anio).days

        for i in range(total):
            try:
                # --- BALANCEO INTELIGENTE (30% Activos / 70% Historial) ---
                # Esto asegura ~30 usuarios activos por cada 100 registros.
                # El gráfico mostrará una tendencia de crecimiento (más ingresos recientes)
                # pero mantendrá barras visibles en los meses anteriores.
                
                if random.random() < 0.30:
                    # 30% son usuarios NUEVOS (0 a 30 días) -> ACTIVOS
                    dias_atras = random.randint(0, 30)
                else:
                    # 70% son usuarios ANTIGUOS (31 días hasta Enero) -> VENCIDOS (Historial)
                    # Validamos que haya días suficientes para evitar error en enero
                    if dias_totales_anio > 31:
                        dias_atras = random.randint(31, dias_totales_anio)
                    else:
                        dias_atras = random.randint(0, dias_totales_anio)

                # Fecha exacta del pasado simulado
                fecha_simulada = timezone.now() - timedelta(days=dias_atras)

                # 2. Crear Usuario
                rut = self.generar_rut_unico()
                first_name = fake.first_name()
                last_name = fake.last_name()
                username = f"{first_name.lower()}.{last_name.lower()}{random.randint(100,999)}"
                
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
                )

                # --- FORZAR FECHA DE REGISTRO DEL USUARIO ---
                # Django pone 'now' por defecto. Aquí lo sobrescribimos manualemente.
                user.date_joined = fecha_simulada
                user.created_at = fecha_simulada
                user.save(update_fields=['date_joined', 'created_at'])

                # 3. Crear Membresía Histórica
                # El 90% de los usuarios creados tendrán una compra asociada a esa fecha
                if random.random() < 0.90:
                    plan = random.choice(planes)
                    
                    # La fecha de inicio del plan es la fecha simulada
                    start_date = fecha_simulada.date()
                    membership = Membership.objects.create(
                        user=user,
                        plan=plan,
                        start_date=start_date,
                        # payment_date se define aquí explícitamente para el gráfico de ingresos
                        payment_date=fecha_simulada, 
                        payment_method=random.choice(['efectivo', 'transferencia', 'tarjeta']),
                        amount_paid=plan.price,
                        notes="Registro histórico generado por script"
                    )
                    
                    # --- FORZAR METADATA DE LA MEMBRESÍA ---
                    # update_fields es clave para saltarse el auto_now_add=True inmutable
                    membership.created_at = fecha_simulada
                    
                    # Calculamos si está vencida o activa basado en la fecha simulada + duración
                    fecha_vencimiento = start_date + timedelta(days=plan.duration_days)
                    membership.end_date = fecha_vencimiento

                    if fecha_vencimiento < timezone.now().date():
                        membership.status = 'expired'
                        membership.is_active = False
                    else:
                        membership.status = 'active'
                        membership.is_active = True
                    
                    # Guardamos los cambios de fecha forzados
                    membership.save()

                    # 4. Generar Accesos Históricos (Si aplica)
                    self.generar_asistencias(user, membership)

                if (i + 1) % 10 == 0:
                    self.stdout.write(self.style.SUCCESS(f'Progreso: {i + 1}/{total} - Fecha: {fecha_simulada.strftime("%Y-%m-%d")}'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'¡Listo! Se inyectaron ingresos desde {fecha_simulada.strftime("%B")} hasta hoy.'))

    def crear_planes_base(self):
        self.stdout.write('Sincronizando planes base...')
        
        # 1. Plan Estudiante
        Plan.objects.update_or_create(
            name="Plan Estudiante",  # USAR NAME COMO IDENTIFICADOR
            defaults={
                'plan_type': 'basico', # El tipo pasa a ser un valor a actualizar/crear
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

        # 2. Plan Intermedio 4 Días
        Plan.objects.update_or_create(
            name="Plan Intermedio 4 Días", # USAR NAME COMO IDENTIFICADOR
            defaults={
                'plan_type': 'estandar',
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

        # 3. Plan Completo
        Plan.objects.update_or_create(
            name="Plan Completo", # USAR NAME COMO IDENTIFICADOR
            defaults={
                'plan_type': 'premium',
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
        # Generar asistencias pasadas si la membresía estuvo activa
        start = membership.start_date
        end = min(membership.end_date, timezone.now().date())
        if start > end: return

        delta = (end - start).days
        for i in range(delta + 1):
            current_day = start + timedelta(days=i)
            # Solo generamos accesos hasta el día de hoy
            if current_day > timezone.now().date():
                break
                
            prob = 0.2 if current_day.weekday() >= 5 else 0.5 
            if random.random() < prob: 
                hora = random.randint(7, 21)
                fecha_acceso = timezone.datetime(
                    current_day.year, current_day.month, current_day.day,
                    hora, random.randint(0, 59), tzinfo=timezone.get_current_timezone()
                )
                # Crear acceso histórico
                AccessLog.objects.create(user=user, timestamp=fecha_acceso, status='allowed', membership=membership)