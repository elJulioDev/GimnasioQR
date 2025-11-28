from django.core.management.base import BaseCommand
from Clientes.models import CustomUser

class Command(BaseCommand):
    help = 'Crea los usuarios base para iniciar el sistema (Admin Web y Moderador)'

    def handle(self, *args, **kwargs):
        self.stdout.write('Inicializando usuarios del sistema...')

        # 1. Crear ADMIN WEB (Para usar el Dashboard /admin-panel/)
        # IMPORTANTE: is_superuser=False para que el login web lo deje pasar
        if not CustomUser.objects.filter(rut='11.111.111-1').exists():
            admin_user = CustomUser.objects.create_user(
                username='administrador',  # Usamos el RUT como username
                email='admin@clubhouse.com',
                password='123',      # Contraseña inicial
                first_name='Administrador',
                last_name='General',
                rut='11.111.111-1',
                role='admin',             # Rol necesario para el panel
                is_staff=True,            # Permiso staff
                is_superuser=False,       # CRUCIAL: False para entrar por web
                is_active=True,
                phone='+56911111111'
            )
            self.stdout.write(self.style.SUCCESS(f'CREADO - Admin Web: RUT {admin_user.rut} / Pass: admin123'))
        else:
            self.stdout.write(self.style.WARNING('El Admin Web ya existe.'))

        # 3. Crear SUPERUSUARIO (Para entrar a /admin de Django en caso de emergencia)
        # Este usuario NO puede entrar al panel web normal por seguridad
        if not CustomUser.objects.filter(is_superuser=True).exists():
            CustomUser.objects.create_superuser(
                username='admin',
                email='root@clubhouse.com',
                password='123'
            )
            self.stdout.write(self.style.SUCCESS('CREADO - Superuser Django: User "admin" / Pass: 123'))
        else:
            self.stdout.write(self.style.WARNING('Ya existe un superusuario.'))