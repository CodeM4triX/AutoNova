from decimal import Decimal

from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import F, Sum, DecimalField

from tienda.models import Producto

User = get_user_model()


class Pedido(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return str(self.id)

    @property
    def total(self):
        resultado = self.lineapedido_set.aggregate(
            total=Sum(
                F('precio') * F('cantidad'),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        return resultado['total'] or Decimal('0.00')

    class Meta:
        db_table = 'pedidos'
        ordering = ['id']


class LineaPedido(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE)
    cantidad = models.IntegerField(default=1)
    precio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.cantidad} unidades de {self.producto.nombre}'

    @property
    def subtotal(self):
        return self.precio * self.cantidad

    class Meta:
        db_table = 'lineapedidos'
        ordering = ['id']


class RankingPedido(models.Model):
    nombre = models.CharField(max_length=255, unique=True)
    ranking = models.IntegerField(blank=False)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = 'rankingpedido'
        verbose_name_plural = 'rankingpedidos'
        ordering = ['-ranking']