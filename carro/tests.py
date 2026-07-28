from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from tienda.test_helpers import crear_producto


class CarroSeguridadTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(sufijo='1', almacen=5)

    def test_agregar_por_get_devuelve_405(self):
        response = self.client.get(
            reverse('carro:agregar_producto', args=[self.producto.id])
        )
        self.assertEqual(response.status_code, 405)

    def test_agregar_por_post_funciona(self):
        response = self.client.post(
            reverse('carro:agregar_producto', args=[self.producto.id])
        )
        self.assertEqual(response.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.reservado, 1)
        session = self.client.session
        self.assertIn(str(self.producto.id), session['carro'])


class CarroReservasTests(TestCase):
    def setUp(self):
        self.producto = crear_producto(sufijo='2', almacen=5, reservado=0)

    def test_eliminar_libera_reservas(self):
        url = reverse('carro:agregar_producto', args=[self.producto.id])
        self.client.post(url)
        self.client.post(url)

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.reservado, 2)

        self.client.post(
            reverse('carro:eliminar_producto', args=[self.producto.id])
        )
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.reservado, 0)

    def test_limpiar_carro_solo_afecta_productos_en_sesion(self):
        otro = crear_producto(sufijo='3', almacen=5)

        self.client.post(
            reverse('carro:agregar_producto', args=[self.producto.id])
        )
        otro.reservado = 3
        otro.save()

        self.client.post(reverse('carro:limpiar_carro'))

        self.producto.refresh_from_db()
        otro.refresh_from_db()
        self.assertEqual(self.producto.reservado, 0)
        self.assertEqual(otro.reservado, 3)