from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
import os
from io import BytesIO
from xhtml2pdf import pisa
import qrcode

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
    Envía el correo de bienvenida generando el QR en memoria.
    """
    try:
        # Contexto para el correo
        context = {
            'user': user,
            'membership': membership,
            'plan_name': membership.plan.name,
            'qr_unique_id': user.qr_unique_id,
            'send_qr': send_qr,
            'send_contract': send_contract
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
        
        # 1. Generar y Adjuntar QR en Memoria (Si se solicitó)
        if send_qr and user.qr_unique_id:
            # Obtener el texto del QR usando el método del modelo
            qr_data = user.get_qr_data()
            
            # Generar imagen QR
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_data)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Guardar en buffer de memoria
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_bytes = buffer.getvalue()
            
            # Adjuntar al correo
            email.attach(f'AccesoQR_{user.rut}.png', qr_bytes, 'image/png')
        
        # 2. Adjuntar Contrato (Igual que antes)
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
    
def generate_pdf_receipt(membership):
    """Genera el PDF del recibo de pago."""
    template_path = 'pdfs/receipt_template.html'
    context = {
        'pago': membership,
        'user': membership.user,
        'fecha_emision': timezone.now()
    }
    html = render_to_string(template_path, context)
    result = BytesIO()
    
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result, encoding='UTF-8')
    
    if not pdf.err:
        return result.getvalue()
    return None