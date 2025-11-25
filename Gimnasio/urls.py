from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from Clientes import views

urlpatterns = [
    # Admin de Django (NO TOCAR)
    path('admin/', admin.site.urls),
    
    # Autenticación
    path('', views.landing_page, name='home'),
    path('login/', views.inicio_sesion, name='inicio_sesion'),
    path('login/procesar/', views.process_login, name='process_login'),
    path('logout/', views.cerrar_sesion, name='cerrar_sesion'),
    
    # Registro
    path('registro/', views.mostrar_registro, name='mostrar_registro'),
    path('registro/procesar/', views.process_registration, name='process_registration'),
    
    # Paneles por rol
    path('admin-panel/', views.index_admin, name='index_admin'),
    path('moderador-panel/', views.index_moderador, name='index_moderador'),
    path('socio-panel/', views.index_socio, name='index_socio'),
    
    # === Gestión de Usuarios (Panel Administrativo) ===
    path('management/users/create/', views.admin_user_create, name='admin_user_create'),
    path('management/users/<int:user_id>/details/', views.admin_user_details, name='admin_user_details'),
    path('management/users/<int:user_id>/edit/', views.admin_user_edit, name='admin_user_edit'),
    path('management/users/<int:user_id>/delete/', views.admin_user_delete, name='admin_user_delete'),
    
    # === Gestión de Planes (Panel Administrativo) ===
    path('management/plans/create/', views.admin_plan_create, name='admin_plan_create'),
    path('management/plans/<int:plan_id>/details/', views.admin_plan_details, name='admin_plan_details'),
    path('management/plans/<int:plan_id>/edit/', views.admin_plan_edit, name='admin_plan_edit'),
    path('management/plans/<int:plan_id>/delete/', views.admin_plan_delete, name='admin_plan_delete'),

    # Otras vistas
    path('qr-scanner/', views.mostrar_Scanner, name='mostrar_Scanner'),
    path('QR/', views.mostrar_QRCodeEmail, name='mostrar_QRCodeEmail'),
    
    # API Endpoints
    path('api/plans/', views.get_plans, name='get_plans'),
    path('api/validate-rut/', views.validate_rut, name='validate_rut'),
    path('api/validate-email/', views.validate_email, name='validate_email'),
    
    # Nueva ruta para procesar QR
    path('api/process-qr-scan/', views.process_qr_scan, name='process_qr_scan'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
