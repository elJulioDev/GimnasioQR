from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from .models import CustomUser

class RUTorEmailBackend(ModelBackend):
    """
    Backend personalizado SOLO para usuarios normales (no superusuarios)
    Los superusuarios SOLO pueden autenticarse en /admin con el backend por defecto
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Si viene del /admin (request path contiene 'admin'), NO usar este backend
        if request and '/admin' in request.path:
            return None  # Dejar que el backend por defecto maneje el admin
        
        try:
            # Buscar usuario por RUT, Email o Username
            user = CustomUser.objects.get(
                Q(rut=username) | Q(email=username) | Q(username=username)
            )
            
            # IMPORTANTE: Rechazar superusuarios en este backend
            if user.is_superuser:
                return None  # Superusuarios NO pueden usar este backend
            
            # Validar contraseña
            if user.check_password(password):
                return user
                
        except CustomUser.DoesNotExist:
            return None
        except CustomUser.MultipleObjectsReturned:
            return None
        
        return None
    
    def get_user(self, user_id):
        try:
            user = CustomUser.objects.get(pk=user_id)
            # No retornar superusuarios en este backend
            if user.is_superuser:
                return None
            return user
        except CustomUser.DoesNotExist:
            return None
