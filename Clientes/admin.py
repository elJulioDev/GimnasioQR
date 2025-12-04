from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import CustomUser, Plan, Membership, AccessLog
import qrcode
import base64
from io import BytesIO

@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    model = CustomUser
    
    # Filtrar por defecto para mostrar solo usuarios de la app (no superusuarios)
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.GET.get('all'):
            return qs.filter(is_superuser=False)
        return qs
    
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 
                   'is_staff', 'is_superuser', 'is_active_member', 'created_at')
    list_filter = ('role', 'is_active_member', 'is_staff', 'is_superuser', 'created_at')
    search_fields = ('rut', 'email', 'first_name', 'last_name', 'username')
    ordering = ('-created_at',)
    
    # --- MÉTODO NUEVO: Generar visualización del QR para el Admin ---
    def display_qr_code(self, obj):
        if obj.qr_unique_id:
            # Obtener datos del modelo
            data_string = obj.get_qr_data()
            if not data_string:
                return "Error en datos QR"

            # Generar QR en memoria
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=4,
                border=1,
            )
            qr.add_data(data_string)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convertir a Base64
            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
            
            # Retornar HTML seguro
            return format_html('<img src="data:image/png;base64,{}" width="150" height="150" style="border:1px solid #ccc; padding:5px;" />', img_str)
        return "Sin Código QR asignado"
    
    display_qr_code.short_description = "Vista Previa QR (Generado)"

    # --- FIELDSETS ACTUALIZADOS ---
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
            'fields': ('display_qr_code', 'qr_unique_id'), # Usamos el método display, no el campo
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
    
    # qr_code eliminado de aquí, agregamos display_qr_code
    readonly_fields = ('display_qr_code', 'qr_unique_id', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        """
        Guardar el modelo con validaciones especiales
        """
        if change:
            # Si cambia el rol y deja de ser socio
            if 'role' in form.changed_data:
                old_role = form.initial.get('role')
                new_role = obj.role
                
                if old_role == 'socio' and new_role != 'socio':
                    # obj.qr_code = None  <-- ELIMINADO
                    obj.qr_unique_id = None
                    obj.is_active_member = False
        
        else:
            if not obj.rut and not obj.is_superuser:
                obj.rut = f"TEMP_{obj.username}"
            
            if not obj.phone:
                obj.phone = ""
            
            if not obj.role and not obj.is_superuser:
                obj.role = 'socio'
        
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