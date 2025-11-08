from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, Plan, Membership, AccessLog


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    model = CustomUser
    
    # Filtrar por defecto para mostrar solo usuarios de la app (no superusuarios)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Mostrar superusuarios separados (opcional)
        if not request.GET.get('all'):
            return qs.filter(is_superuser=False)
        return qs
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 
                   'is_staff', 'is_superuser', 'is_active_member', 'created_at')
    list_filter = ('role', 'is_active_member', 'is_staff', 'is_superuser', 'created_at')
    search_fields = ('rut', 'email', 'first_name', 'last_name', 'username')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información Personal', {'fields': ('first_name', 'last_name', 'email')}),
        ('Información del Socio', {
            'fields': ('rut', 'phone', 'birthdate', 'role', 'is_active_member'),
            'description': 'Solo para usuarios de la aplicación (no superusuarios)'
        }),
        ('Permisos', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Código QR', {
            'fields': ('qr_code', 'qr_unique_id'),
            'classes': ('collapse',)
        }),
        ('Fechas Importantes', {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
        ('Tipo de Usuario', {
            'classes': ('wide',),
            'fields': ('is_staff', 'is_superuser'),
            'description': 'is_superuser = Admin Django | is_staff sin superuser = Usuario de la app'
        }),
        ('Información Adicional', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'rut', 'phone', 'birthdate', 'role'),
            'description': 'Solo necesario para usuarios de la app (no superusuarios)'
        }),
    )
    
    readonly_fields = ('qr_code', 'qr_unique_id', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        """
        Guardar el modelo con validaciones especiales
        """
        # Si es una edición (change=True)
        if change:
            # Limpiar campos relacionados con QR si el rol cambió de 'socio' a otro
            if 'role' in form.changed_data:
                old_role = form.initial.get('role')
                new_role = obj.role
                
                # Si deja de ser socio, limpiar QR
                if old_role == 'socio' and new_role != 'socio':
                    obj.qr_code = None
                    obj.qr_unique_id = None
                    obj.is_active_member = False
        
        # Si es un nuevo usuario (change=False)
        else:
            # Asegurar valores por defecto para campos obligatorios
            if not obj.rut and not obj.is_superuser:
                obj.rut = f"TEMP_{obj.username}"
            
            if not obj.phone:
                obj.phone = ""
            
            # Si no tiene rol y no es superusuario, asignar 'socio' por defecto
            if not obj.role and not obj.is_superuser:
                obj.role = 'socio'
        
        # Guardar el modelo
        super().save_model(request, obj, form, change)

@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'price', 'duration_days', 'is_active')
    list_filter = ('is_active', 'includes_classes', 'includes_nutritionist')
    search_fields = ('name', 'description')
    ordering = ('price',)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'start_date', 'end_date', 
                   'status', 'is_active', 'days_remaining')
    list_filter = ('status', 'is_active', 'plan', 'payment_method')
    search_fields = ('user__rut', 'user__first_name', 'user__last_name', 'user__email')
    date_hierarchy = 'start_date'
    ordering = ('-created_at',)
    
    readonly_fields = ('created_at', 'updated_at', 'days_remaining')
    
    def days_remaining(self, obj):
        return obj.days_remaining()
    days_remaining.short_description = 'Días Restantes'


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'timestamp', 'status', 'membership')
    list_filter = ('status', 'timestamp')
    search_fields = ('user__rut', 'user__first_name', 'user__last_name', 'user__email')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    readonly_fields = ('timestamp',)
