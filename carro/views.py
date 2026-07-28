from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .carro import Carro
from tienda.models import Producto


def cesta(request):
    return render(request, 'carro/cesta.html')


def _redirect_back(request):
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', reverse('tienda')))


def ejecutar_limpiar_carro(request):
    """Lógica del carrito sin HTTP. La usa logout u otras vistas internas."""
    carro = Carro(request)

    for value in carro.carro.values():
        try:
            producto = Producto.objects.get(id=value['producto_id'])
            producto.reservado = max(0, producto.reservado - value['cantidad'])
            producto.save()
        except Producto.DoesNotExist:
            pass

    carro.limpiar_carro()


@require_POST
def agregar_producto(request, producto_id):
    carro = Carro(request)
    producto = get_object_or_404(Producto, id=producto_id)

    almacen = producto.almacen or 0
    if almacen > producto.reservado:
        carro.agregar(producto)
        producto.reservado += 1
        producto.save()

    return _redirect_back(request)


@require_POST
def eliminar_producto(request, producto_id):
    carro = Carro(request)
    producto = get_object_or_404(Producto, id=producto_id)

    item = carro.carro.get(str(producto_id))
    cantidad = item['cantidad'] if item else 0

    carro.eliminar(producto)

    if cantidad > 0:
        producto.reservado = max(0, producto.reservado - cantidad)
        producto.save()

    return _redirect_back(request)


@require_POST
def restar_producto(request, producto_id):
    carro = Carro(request)
    producto = get_object_or_404(Producto, id=producto_id)

    if producto.reservado > 0:
        carro.restar_producto(producto)
        producto.reservado -= 1
        producto.save()

    return _redirect_back(request)


@require_POST
def limpiar_carro(request):
    ejecutar_limpiar_carro(request)
    return _redirect_back(request)