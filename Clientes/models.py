from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.utils import timezone
from datetime import timedelta, date
import qrcode
from io import BytesIO
from django.core.files import File
import hashlib


class CustomUserManager(UserManager):
    """Manager personalizado que diferencia entre superusuarios y usuarios normales"""
    
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """
        Override para crear superusuarios SIN asignarles rol de socio y 
        SIN campos obligatorios que no sean necesarios para el admin
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        # Los superusuarios NO tienen rol porque NO son parte del sistema de socios
        if 'role' not in extra_fields:
            extra_fields['role'] = None  # Superusuarios sin rol
        
        # Asegurarse de que los campos opcionales sean None
        extra_fields.setdefault('rut', None)
        extra_fields.setdefault('phone', None)
        extra_fields.setdefault('birthdate', None)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    """Modelo de usuario personalizado que extiende AbstractUser"""
    
    ROLE_CHOICES = (
        ('admin', 'Administrador'),
        ('moderador', 'Moderador'),
        ('socio', 'Socio'),
    )
    
    objects = CustomUserManager()  # Usar el manager personalizado
    
    # Campos adicionales - TODOS OPCIONALES
    rut = models.CharField(max_length=12, unique=True, verbose_name="RUT", null=True, blank=True)
    phone = models.CharField(max_length=15, verbose_name="Teléfono", null=True, blank=True)
    birthdate = models.DateField(verbose_name="Fecha de Nacimiento", null=True, blank=True)
    role = models.CharField(
        max_length=10, 
        choices=ROLE_CHOICES, 
        null=True,  # AÑADIDO: Permite NULL para superusuarios
        blank=True,
        verbose_name="Rol"
    )
    
    # QR Code
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True, verbose_name="Código QR")
    qr_unique_id = models.CharField(max_length=64, unique=True, blank=True, null=True, verbose_name="ID Único QR")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")
    is_active_member = models.BooleanField(default=False, verbose_name="Socio Activo")
    
    # Related names para evitar conflictos
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name='customuser_set',
        related_query_name='customuser',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name='customuser_set',
        related_query_name='customuser',
    )
    
    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ['-created_at']
    
    def __str__(self):
        if self.is_superuser:
            return f"SUPERUSER: {self.username}"
        if self.rut:
            return f"{self.get_full_name()} ({self.rut})"
        return self.get_full_name() or self.username
    
    def save(self, *args, **kwargs):
        """
        Override del método save.
        IMPORTANTE: NO genera QR ni asigna rol a superusuarios
        """
        # Si es superuser, guardar y salir
        if self.is_superuser:
            super().save(*args, **kwargs)
            return
    
        # Para usuarios normales (no superusuarios)
        is_new = self.pk is None  # Verificar si es un nuevo usuario
    
        # Generar qr_unique_id si es socio y tiene RUT
        if self.role == 'socio' and self.rut and not self.qr_unique_id:
            unique_string = f"{self.rut}-{timezone.now().timestamp()}"
            self.qr_unique_id = hashlib.sha256(unique_string.encode()).hexdigest()
    
        # ✅ SIEMPRE hacer el save principal
        super().save(*args, **kwargs)
    
        # Generar QR después del save (si es necesario)
        if self.role == 'socio' and self.rut and not self.qr_code:
            self.generate_qr_code()

    
    def generate_qr_code(self):
        """Genera QR solo para socios"""
        if not self.rut or self.is_superuser:
            return
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
        qr_data = {
            'user_id': self.id,
            'qr_id': self.qr_unique_id,
            'rut': self.rut
        }
        
        qr.add_data(str(qr_data))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        filename = f'qr_{self.rut}_{self.id}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        super().save(update_fields=['qr_code'])
    
    def get_active_membership(self):
        """Retorna la membresía activa del usuario o None."""
        if self.is_superuser:
            return None
        return self.memberships.filter(
            is_active=True,
            end_date__gt=timezone.now().date()  # CAMBIADO: > en lugar de >=
        ).first()
    
    def has_active_membership(self):
        """Verifica si el usuario tiene una membresía activa."""
        if self.is_superuser:
            return False
        return self.memberships.filter(
            is_active=True,
            end_date__gt=timezone.now().date()  # CAMBIADO: > en lugar de >=
        ).exists()


class Plan(models.Model):
    """Modelo para los planes de membresía del gimnasio."""
    
    PLAN_TYPE_CHOICES = (
        ('finde', 'Plan Finde'),
        ('diario', 'Plan Diario'),
        ('completo', 'Plan Completo'),
    )
    
    name = models.CharField(max_length=50, verbose_name="Nombre del Plan")
    plan_type = models.CharField(
        max_length=10,
        choices=PLAN_TYPE_CHOICES,
        unique=True,
        verbose_name="Tipo de Plan"
    )
    description = models.TextField(verbose_name="Descripción")
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Precio")
    duration_days = models.IntegerField(default=30, verbose_name="Duración en Días")
    access_days = models.CharField(
        max_length=100,
        help_text="Ej: Lunes a Viernes, Fines de semana, Todos los días",
        verbose_name="Días de Acceso"
    )
    includes_classes = models.BooleanField(default=False, verbose_name="Incluye Clases Grupales")
    includes_nutritionist = models.BooleanField(default=False, verbose_name="Incluye Nutricionista")
    benefits = models.TextField(
        blank=True,
        null=True,
        verbose_name="Beneficios",
        help_text="Lista de beneficios separados por comas"
    )
    is_active = models.BooleanField(default=True, verbose_name="Plan Activo")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - ${self.price:,.0f}"


class Membership(models.Model):
    """
    Modelo para las membresías de los usuarios.
    Relaciona un usuario con un plan y gestiona las fechas de vigencia.
    """
    
    PAYMENT_METHOD_CHOICES = (
        ('efectivo', 'Efectivo'),
        ('transferencia', 'Transferencia'),
        ('tarjeta', 'Tarjeta'),
        ('webpay', 'Webpay'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pendiente'),
        ('active', 'Activa'),
        ('expired', 'Vencida'),
        ('cancelled', 'Cancelada'),
    )
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name="Usuario"
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='memberships',
        verbose_name="Plan"
    )
    
    # Fechas
    start_date = models.DateField(verbose_name="Fecha de Inicio")
    end_date = models.DateField(verbose_name="Fecha de Vencimiento")
    
    # Pago
    payment_method = models.CharField(
        max_length=15,
        choices=PAYMENT_METHOD_CHOICES,
        verbose_name="Método de Pago"
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=0, verbose_name="Monto Pagado")
    payment_date = models.DateTimeField(default=timezone.now, verbose_name="Fecha de Pago")
    
    # Estado
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Estado"
    )
    is_active = models.BooleanField(default=False, verbose_name="Activa")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True, verbose_name="Notas")
    
    class Meta:
        verbose_name = "Membresía"
        verbose_name_plural = "Membresías"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.plan.name} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Override del save para calcular fecha de vencimiento y actualizar estado."""
        
        # ✅ CORREGIDO: Calcular end_date correctamente
        if not self.end_date:
            # Sumar la duración completa del plan
            self.end_date = self.start_date + timedelta(days=self.plan.duration_days)
        
        # Actualizar estado basado en fecha
        # ✅ CORREGIDO: Usar > en lugar de >= para la comparación
        if self.end_date <= timezone.now().date():
            self.status = 'expired'
            self.is_active = False
        elif self.status == 'pending':
            self.status = 'active'
            self.is_active = True
        
        super().save(*args, **kwargs)
        
        # Actualizar estado del usuario
        self.user.is_active_member = self.is_active
        self.user.save(update_fields=['is_active_member'])
    
    def is_valid(self):
        """Verifica si la membresía está vigente."""
        # ✅ CORREGIDO: Usar > en lugar de >=
        return self.is_active and self.end_date > timezone.now().date()
    
    def days_remaining(self):
        """Calcula los días restantes de la membresía."""
        if self.end_date > timezone.now().date():
            return (self.end_date - timezone.now().date()).days
        return 0
    
    def days_until_expiration(self):
        """Alias para days_remaining - usado en las templates"""
        return self.days_remaining()


class AccessLog(models.Model):
    """Modelo para registrar los accesos al gimnasio mediante QR."""
    
    STATUS_CHOICES = (
        ('allowed', 'Permitido'),
        ('denied', 'Denegado'),
    )
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='access_logs',
        verbose_name="Usuario"
    )
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Fecha y Hora")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, verbose_name="Estado")
    membership = models.ForeignKey(
        Membership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Membresía"
    )
    denial_reason = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Razón de Denegación"
    )
    
    class Meta:
        verbose_name = "Registro de Acceso"
        verbose_name_plural = "Registros de Acceso"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.status} - {self.timestamp}"
