from decimal import Decimal
from django.conf import settings


def importe_total_carro(request):
    total = Decimal('0.00')
    if 'carro' in request.session:
        for key, value in request.session['carro'].items():
            total += Decimal(value['precio'])
    return {'importe_total_carro': total}


def whatsapp_number(request):
    """Expose WHATSAPP_NUMBER (digits-only) to templates as `WHATSAPP_NUMBER`."""
    return {'WHATSAPP_NUMBER': getattr(settings, 'WHATSAPP_NUMBER', '')}