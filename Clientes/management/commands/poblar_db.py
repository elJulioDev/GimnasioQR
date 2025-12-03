import random, calendar
from django.core.management.base import BaseCommand
from django.utils import timezone
from faker import Faker
from datetime import timedelta
from Clientes.models import CustomUser, Plan, Membership, AccessLog

# Configuración de Faker para español de Chile
fake = Faker(['es_CL'])

class Command(BaseCommand):
    help = 'Puebla la base de datos definiendo cantidades exactas por mes (Ej: --enero 10 --marzo 5)'

    def add_arguments(self, parser):
        # Argumentos opcionales para cada mes del año
        parser.add_argument('--enero', type=int, default=15, help='Propósitos de año nuevo')
        parser.add_argument('--febrero', type=int, default=10, help='Vacaciones (baja leve)')
        parser.add_argument('--marzo', type=int, default=20, help='Vuelta a clases/trabajo (peak)')
        parser.add_argument('--abril', type=int, default=12, help='Mantención')
        parser.add_argument('--mayo', type=int, default=10, help='Comienzo del frío')
        parser.add_argument('--junio', type=int, default=8, help='Invierno/Lluvias (baja)')
        parser.add_argument('--julio', type=int, default=8, help='Invierno/Vacaciones invierno (baja)')
        parser.add_argument('--agosto', type=int, default=10, help='Pasando agosto')
        parser.add_argument('--septiembre', type=int, default=15, help='Pre-18 y primavera')
        parser.add_argument('--octubre', type=int, default=20, help='Operación verano (subida)')
        parser.add_argument('--noviembre', type=int, default=25, help='Full verano (peak)')
        parser.add_argument('--diciembre', type=int, default=12, help='Fiestas y gastos (baja leve)')

    def handle(self, *args, **kwargs):
        self.crear_planes_base()
        planes = list(Plan.objects.filter(is_active=True))

        if not planes:
            self.stdout.write(self.style.ERROR('No hay planes activos. Imposible crear registros.'))
            return

        now = timezone.now()
        current_year = now.year

        # Mapeo de argumentos a números de mes
        configuracion_meses = [
            (1, kwargs['enero']), (2, kwargs['febrero']), (3, kwargs['marzo']),
            (4, kwargs['abril']), (5, kwargs['mayo']), (6, kwargs['junio']),
            (7, kwargs['julio']), (8, kwargs['agosto']), (9, kwargs['septiembre']),
            (10, kwargs['octubre']), (11, kwargs['noviembre']), (12, kwargs['diciembre'])
        ]

        total_creados = 0

        for mes_num, cantidad in configuracion_meses:
            if cantidad > 0:
                self.stdout.write(f"--- Procesando MES {mes_num} ({cantidad} usuarios) ---")
                
                # Obtener el último día de ese mes
                _, last_day = calendar.monthrange(current_year, mes_num)
                
                # Si estamos creando datos en el mes actual, no pasarnos del día de hoy
                if mes_num == now.month:
                    last_day = min(last_day, now.day)
                
                # Si pedimos datos para un mes futuro (ej: Diciembre si estamos en Noviembre), avisar y saltar
                if mes_num > now.month: # Opcional: Si quieres permitir futuro, borra este if
                    self.stdout.write(self.style.WARNING(f"Saltando Mes {mes_num} porque es futuro."))
                    continue

                for i in range(cantidad):
                    try:
                        # 1. FECHAS
                        dia_random = random.randint(1, last_day)
                        
                        # Fecha de inicio (y de pago)
                        fecha_registro = timezone.datetime(current_year, mes_num, dia_random, 
                                                         random.randint(9, 21), random.randint(0, 59),
                                                         tzinfo=timezone.get_current_timezone())
                        start_date = fecha_registro.date()

                        # Plan y Vencimiento
                        plan = random.choice(planes)
                        end_date = start_date + timedelta(days=plan.duration_days)
                        
                        # Estado real hoy
                        is_active = end_date >= now.date()
                        status = 'active' if is_active else 'expired'

                        # 2. CREAR USUARIO
                        rut = self.generar_rut_unico()
                        first_name = fake.first_name()
                        last_name = fake.last_name()
                        email = f"{first_name}.{last_name}_{mes_num}_{i}@example.com".lower()

                        user = CustomUser.objects.create_user(
                            username=rut,
                            email=email,
                            rut=rut,
                            password='password123',
                            first_name=first_name,
                            last_name=last_name,
                            phone=f"+569{random.randint(10000000, 99999999)}",
                            birthdate=fake.date_of_birth(minimum_age=18, maximum_age=60),
                            role='socio'
                        )
                        
                        # Ajustar fecha de registro del usuario para que coincida con el mes
                        user.date_joined = fecha_registro
                        user.save()

                        # 3. CREAR MEMBRESÍA (Con Ingreso en el mes correcto)
                        membership = Membership.objects.create(
                            user=user,
                            plan=plan,
                            start_date=start_date,
                            end_date=end_date,
                            amount_paid=plan.price,
                            payment_method=random.choice(['efectivo', 'transferencia', 'tarjeta']),
                            payment_date=fecha_registro, # <--- CLAVE PARA TUS GRÁFICOS
                            status=status,
                            is_active=is_active
                        )

                        # 4. HISTORIAL DE ACCESOS
                        self.generar_asistencias(user, membership)
                        
                        total_creados += 1

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f'¡Listo! Total usuarios creados: {total_creados}'))

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