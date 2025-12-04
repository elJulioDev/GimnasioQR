import qrcode
import base64
from io import BytesIO
from django import template

register = template.Library()

@register.simple_tag
def generate_qr_base64(data_string):
    """
    Genera un código QR en formato Base64 para ser incrustado directamente
    en una etiqueta <img> HTML.
    Uso en template: <img src="{% generate_qr_base64 user.get_qr_data %}" ...>
    """
    if not data_string:
        return ""

    # Configuración del QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    qr.add_data(data_string)
    qr.make(fit=True)
    
    # Crear imagen en memoria
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    
    # Convertir a Base64
    img_str = base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    # Retornar string formateado para src de imagen
    return f"data:image/png;base64,{img_str}"