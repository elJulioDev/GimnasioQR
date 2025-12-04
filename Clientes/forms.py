from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    """
    Formulario extendido para la creación de usuarios.
    """
    
    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 
                 'rut', 'phone', 'birthdate', 'role')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar widgets y placeholders
        self.fields['rut'].widget.attrs.update({
            'placeholder': '12.345.678-9',
            'class': 'form-control'
        })
        self.fields['email'].widget.attrs.update({
            'placeholder': 'correo@ejemplo.com',
            'class': 'form-control'
        })
        # Agregar más personalizaciones según necesites


class CustomUserChangeForm(UserChangeForm):
    """
    Formulario para editar usuarios.
    """
    
    class Meta:
        model = CustomUser
        fields = ('email', 'first_name', 'last_name', 'phone', 'role')
