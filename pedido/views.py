from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db import transaction

from carro.carro import Carro
from tienda.models import Producto
from .models import Pedido, LineaPedido, RankingPedido
from django.conf import settings
from propietario.models import PropietarioInfo


@login_required(login_url="/iniciar_session")
@require_POST
def procesar_pedido(request):
    carro = Carro(request)

    if not carro.carro:
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('carro:cesta')

    try:
        with transaction.atomic():
            pedido = Pedido.objects.create(user=request.user)
            lineas_pedido = []

            for value in carro.carro.values():
                producto = Producto.objects.select_for_update().get(
                    id=value['producto_id']
                )
                cantidad = value['cantidad']
                almacen = producto.almacen or 0

                if almacen < cantidad:
                    raise ValueError(
                        f'Stock insuficiente para "{producto.nombre}". '
                        f'Disponible: {almacen}, solicitado: {cantidad}.'
                    )

                lineas_pedido.append(LineaPedido(
                    producto=producto,
                    cantidad=cantidad,
                    precio=producto.precio,
                    user=request.user,
                    pedido=pedido,
                ))
                ranking(producto.nombre, cantidad)
                actualizar_almacen(producto, cantidad)

            LineaPedido.objects.bulk_create(lineas_pedido)

    except ValueError as e:
        messages.error(request, str(e))
        return redirect('carro:cesta')
    except Producto.DoesNotExist:
        messages.error(request, 'Un producto del carrito ya no existe.')
        return redirect('carro:cesta')

    enviar_mail(
        pedido=pedido,
        lineas_pedido=lineas_pedido,
        nombre_usuario=request.user.username,
        email_usuario=request.user.email,
    )

    carro.limpiar_carro()
    messages.success(request, 'El pedido se ha creado correctamente.')
    return redirect('tienda')

def enviar_mail(**kwargs):
    email_usuario = kwargs.get('email_usuario')
    pedido = kwargs.get('pedido')
    lineas_pedido = kwargs.get('lineas_pedido')
    nombre_usuario = kwargs.get('nombre_usuario')

    if not email_usuario:
        return

    # 1. RECUPERAR EL EMAIL DEL PROPIETARIO DESDE LA BASE DE DATOS
    propietario = PropietarioInfo.objects.first()
    email_propietario = propietario.email if propietario else None

    # Datos básicos del servidor
    from_email = settings.DEFAULT_FROM_EMAIL
    contexto_comun = {
        'pedido': pedido,
        'lineas_pedido': lineas_pedido,
        'nombre_usuario': nombre_usuario,
        'email_usuario': email_usuario,
    }

    # ==========================================
    # CORREO 1: Para el Cliente (Pedido exitoso)
    # ==========================================
    asunto_cliente = 'Pedido exitoso - AlphaMarket'
    html_cliente = render_to_string('emails/pedido.html', contexto_comun)
    texto_cliente = strip_tags(html_cliente)

    send_mail(
        asunto_cliente,
        texto_cliente,
        from_email,
        [email_usuario],
        html_message=html_cliente,
    )

    # ==========================================
    # CORREO 2: Para el Propietario (Nueva Venta)
    # ==========================================
    if email_propietario:
        asunto_propietario = f'¡Nueva Venta Registrada! - Pedido #{pedido.id}'

        # Opcional: Puedes usar la misma plantilla o crear una nueva para el dueño (ej. 'emails/nueva_venta.html')
        html_propietario = render_to_string(
            'emails/pedido.html', contexto_comun
        )
        texto_propietario = strip_tags(html_propietario)

        send_mail(
            asunto_propietario,
            texto_propietario,
            from_email,
            [email_propietario],  # Destinatario: El dueño
            html_message=html_propietario,
        )
"""
def enviar_mail(**kwargs):
    email_usuario = kwargs.get('email_usuario')
    if not email_usuario:
        return

    asunto = 'Pedido exitoso - AlphaMarket'
    mensaje = render_to_string('emails/pedido.html', {
        'pedido': kwargs.get('pedido'),
        'lineas_pedido': kwargs.get('lineas_pedido'),
        'nombre_usuario': kwargs.get('nombre_usuario'),
        'email_usuario': email_usuario,
    })
    mensaje_texto = strip_tags(mensaje)
    from_email = settings.DEFAULT_FROM_EMAIL

    send_mail(
        asunto,
        mensaje_texto,
        from_email,
        [email_usuario],
        html_message=mensaje,
    )

"""
def ranking(nombre, cantidad):
    try:
        pedido = RankingPedido.objects.get(nombre=nombre)
        pedido.ranking += cantidad
        pedido.save()
    except ObjectDoesNotExist:
        RankingPedido.objects.create(nombre=nombre, ranking=cantidad)


def actualizar_almacen(producto, cantidad):
    producto.almacen = (producto.almacen or 0) - cantidad
    producto.reservado = max(0, producto.reservado - cantidad)
    if producto.almacen <= 0:
        producto.disponibilidad = False
    producto.save()