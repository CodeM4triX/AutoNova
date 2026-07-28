from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from carro.carro import Carro
from tienda.test_helpers import crear_producto
from .models import Pedido, LineaPedido, RankingPedido
from decimal import Decimal

class PedidoModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', email='test@example.com'
        )
        self.producto = crear_producto(sufijo='ped', precio=Decimal('10.00'))
        self.pedido = Pedido.objects.create(user=self.user)

    def test_total_calcula_precio_por_cantidad(self):
        LineaPedido.objects.create(
            user=self.user,
            producto=self.producto,
            pedido=self.pedido,
            cantidad=3,
            precio=Decimal('10.00'),
        )
        self.assertEqual(self.pedido.total, Decimal('30.00'))

    def test_subtotal_linea(self):
        linea = LineaPedido.objects.create(
            user=self.user,
            producto=self.producto,
            pedido=self.pedido,
            cantidad=2,
            precio=Decimal('15.00'),
        )
        self.assertEqual(linea.subtotal, Decimal('30.00'))
    def test_precision_decimal(self):
        LineaPedido.objects.create(
            user=self.user,
            producto=self.producto,
            pedido=self.pedido,
            cantidad=3,
            precio=Decimal('10.10'),
        )
        self.assertEqual(self.pedido.total, Decimal('30.30'))

@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class ProcesarPedidoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer', password='testpass123', email='buyer@example.com'
        )
        self.producto = crear_producto(sufijo='buy', precio=Decimal('20.00'), almacen=10)
        self.client.login(username='buyer', password='testpass123')

    def test_carrito_vacio_no_crea_pedido(self):
        response = self.client.post(reverse('procesar_pedido'))
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertRedirects(response, reverse('carro:cesta'))

    def test_procesar_pedido_actualiza_stock_y_limpia_carrito(self):
        self.client.post(
            reverse('carro:agregar_producto', args=[self.producto.id])
        )
        self.client.post(
            reverse('carro:agregar_producto', args=[self.producto.id])
        )

        response = self.client.post(reverse('procesar_pedido'))
        self.assertRedirects(response, reverse('tienda'))
        self.assertEqual(Pedido.objects.count(), 1)

        pedido = Pedido.objects.first()
        self.assertEqual(pedido.lineapedido_set.count(), 1)
        self.assertEqual(pedido.total, Decimal('40.00'))

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.almacen, 8)
        self.assertEqual(self.producto.reservado, 0)

        session = self.client.session
        self.assertEqual(session.get('carro', {}), {})

    def test_procesar_pedido_envia_email(self):
        self.client.post(
            reverse('carro:agregar_producto', args=[self.producto.id])
        )
        self.client.post(reverse('procesar_pedido'))

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('buyer@example.com', mail.outbox[0].to)

    def test_stock_insuficiente_no_crea_pedido(self):
        self.producto.almacen = 1
        self.producto.save()

        session = self.client.session
        session['carro'] = {
            str(self.producto.id): {
                'producto_id': self.producto.id,
                'nombre': self.producto.nombre,
                'costo': '20.0',
                'precio': '40.0',
                'cantidad': 2,
                'imagen': '/static/img/default.png',
            }
        }
        session.save()

        response = self.client.post(reverse('procesar_pedido'))
        self.assertEqual(Pedido.objects.count(), 0)
        self.assertRedirects(response, reverse('carro:cesta'))

    def test_requiere_login(self):
        self.client.logout()
        response = self.client.post(reverse('procesar_pedido'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/iniciar_session', response.url)