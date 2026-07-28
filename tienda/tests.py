from django.test import TestCase, override_settings
from django.urls import reverse

from .test_helpers import crear_catalogo_base, crear_producto
from .models import Producto


@override_settings(TIENDA_PRODUCTOS_POR_PAGINA=2)
class CategoriaPaginacionTests(TestCase):
    def setUp(self):
        base = crear_catalogo_base()
        self.categoria = base['categoria']
        for i in range(5):
            Producto.objects.create(
                nombre=f'Prod {i}',
                precio=10 + i,
                almacen=5,
                marca=base['marca'],
                modelo=base['modelo'],
                sistema=base['sistema'],
                categoria=base['categoria'],
                producto_marca=base['producto_marca'],
            )

    def test_pagina_1_muestra_2_productos(self):
        response = self.client.get(
            reverse('categoria', args=[self.categoria.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['productos']), 2)

    def test_pagina_2_muestra_resto(self):
        response = self.client.get(
            reverse('categoria', args=[self.categoria.id]) + '?page=2'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['productos']), 2)

    def test_pagina_invalida_redirige_a_ultima_valida(self):
        response = self.client.get(
            reverse('categoria', args=[self.categoria.id]) + '?page=999'
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['productos'].number, 3)


class CategoriaViewTests(TestCase):
    def test_categoria_inexistente_devuelve_404(self):
        response = self.client.get(reverse('categoria', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_tienda_responde_200(self):
        response = self.client.get(reverse('tienda'))
        self.assertEqual(response.status_code, 200)