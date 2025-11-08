from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
import os

def send_qr_email(user, membership):
    """
    Envía el código QR por correo electrónico al usuario.
    
    Args:
        user: CustomUser instance
        membership: Membership instance
    
    Returns:
        bool: True si se envió exitosamente, False en caso contrario
    """
    try:
        # Contexto para el template del email
        context = {
            'user': user,
            'membership': membership,
            'plan_name': membership.plan.name,
            'qr_unique_id': user.qr_unique_id,
        }
        
        # Renderizar el template HTML del email
        html_message = render_to_string('emails/qr_code_email.html', context)
        
        # Crear el mensaje de email
        subject = f'¡Bienvenido a ClubHouse Digital, {user.first_name}!'
        
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        
        email.content_subtype = 'html'  # Importante para enviar HTML
        
        # Adjuntar el QR code
        if user.qr_code and os.path.exists(user.qr_code.path):
            with open(user.qr_code.path, 'rb') as qr_file:
                email.attach(
                    f'QR_Code_{user.rut}.png',
                    qr_file.read(),
                    'image/png'
                )
        
        # Enviar el email
        email.send(fail_silently=False)
        return True
        
    except Exception as e:
        print(f"Error al enviar email: {str(e)}")
        return False
