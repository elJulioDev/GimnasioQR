from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import os
from io import BytesIO
from xhtml2pdf import pisa

def generate_pdf_contract(user, membership):
    """Genera el PDF del contrato y lo devuelve como bytes."""
    template_path = 'pdfs/contract_template.html'
    context = {
        'user': user,
        'membership': membership,
        'fecha_actual': timezone.now()
    }
    html = render_to_string(template_path, context)
    result = BytesIO()
    
    # CORRECCIÓN 1: Usar UTF-8 explícitamente para soportar tildes y ñ
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, encoding='UTF-8')
    
    if not pdf.err:
        return result.getvalue()
    return None

def send_qr_email(user, membership, send_qr=False, send_contract=False):
    """
    Envía el correo de bienvenida con los adjuntos seleccionados.
    """
    try:
        # Contexto para el correo
        context = {
            'user': user,
            'membership': membership,
            'plan_name': membership.plan.name,
            'qr_unique_id': user.qr_unique_id,
            'send_qr': send_qr,          # Pasamos flags al template
            'send_contract': send_contract # Pasamos flags al template
        }
        
        html_message = render_to_string('emails/qr_code_email.html', context)
        subject = f'¡Bienvenido al Club, {user.first_name}! 🚀'
        
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.content_subtype = 'html'
        
        # CORRECCIÓN 2: Lógica separada para adjuntos
        
        # 1. Adjuntar QR SOLO si se solicitó (send_qr=True)
        if send_qr and user.qr_code and os.path.exists(user.qr_code.path):
            with open(user.qr_code.path, 'rb') as qr_file:
                email.attach(f'AccesoQR_{user.rut}.png', qr_file.read(), 'image/png')
        
        # 2. Adjuntar Contrato SOLO si se solicitó (send_contract=True)
        if send_contract:
            pdf_content = generate_pdf_contract(user, membership)
            if pdf_content:
                filename = f"Contrato_Servicio_{user.rut}.pdf"
                email.attach(filename, pdf_content, 'application/pdf')
        
        email.send(fail_silently=False)
        return True
        
    except Exception as e:
        print(f"Error enviando email: {str(e)}")
        return False