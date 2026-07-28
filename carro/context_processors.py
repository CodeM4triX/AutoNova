from decimal import Decimal


def importe_total_carro(request):
    total = Decimal('0.00')
    if 'carro' in request.session:
        for key, value in request.session['carro'].items():
            total += Decimal(value['precio'])
    return {'importe_total_carro': total}