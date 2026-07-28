from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from . import app_settings
from django.core.exceptions import ValidationError

# Create your models here.
class Marca(models.Model):
    nombre = models.CharField(max_length=app_settings.NAME_MAX_LENGTH)
    logo = models.ImageField(upload_to='tienda/marca', null=True, blank=True)

    class Meta:
        verbose_name = 'marca'
        verbose_name_plural= 'marcas'

    def __str__(self):
        return self.nombre

class Modelo(models.Model):
    nombre = models.CharField(max_length=100)
    generacion = models.CharField(max_length=20, blank=True)
    chasis = models.CharField(max_length=20, blank=True)
    anios_produccion = models.CharField(max_length=20, blank=True)

    marca = models.ForeignKey(Marca, on_delete=models.CASCADE)

    class Meta:
        ordering = ['nombre']
        verbose_name = "modelo"
        verbose_name_plural = "modelos"

    def __str__(self):
        return f"{self.nombre} {self.generacion} ({self.chasis}) ({self.anios_produccion})"

class Sistema(models.Model):
    nombre = models.CharField(max_length=app_settings.NAME_MAX_LENGTH)
    logo = models.ImageField(upload_to='tienda/sistema', null=True, blank=True)

    class Meta:
        verbose_name = 'sistema'
        verbose_name_plural= 'sistemas'

    def __str__(self):
        return self.nombre

class Categoria(models.Model):
    nombre = models.CharField(max_length=app_settings.NAME_MAX_LENGTH)
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'categoria'
        verbose_name_plural= 'categorias'

    def __str__(self):
        return self.nombre

class ProductoMarca(models.Model):
    nombre = models.CharField(max_length=app_settings.NAME_MAX_LENGTH)
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE)
    logo = models.ImageField(upload_to='tienda/sis_marca', null=True, blank=True)

    class Meta:
        verbose_name = 'producto_marca'
        verbose_name_plural= 'producto_marcas'

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    nombre = models.CharField(max_length=app_settings.NAME_MAX_LENGTH)
    marca = models.ForeignKey(Marca, on_delete=models.CASCADE)
    modelo = models.ForeignKey(Modelo, on_delete=models.CASCADE)
    sistema = models.ForeignKey(Sistema, on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE)
    producto_marca = models.ForeignKey(ProductoMarca, on_delete=models.CASCADE)

    #imagen = models.ImageField(upload_to='tienda/producto', null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    almacen = models.IntegerField(blank=True, null=True)
    disponibilidad = models.BooleanField(default=True)
    reservado = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'producto'
        verbose_name_plural = 'productos'
    
    def __str__(self):
        return self.nombre

# Modelo para almacenar imágenes adicionales de un producto
class ImagenProducto(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="imagenes"
    )
    imagen = models.ImageField(upload_to="tienda/producto")

    def __str__(self):
        return self.producto.nombre

# Modelo para almacenar detalles de una categoría
class DetalleCategoria(models.Model):
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    nombre = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.categoria.nombre} - {self.nombre}"

# Modelo para almacenar valores de detalles de un producto
class ValorDetalleProducto(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="detalles"
    )

    detalle = models.ForeignKey(
        DetalleCategoria,
        on_delete=models.CASCADE,
        related_name="valores"
    )
    # detalle.valores.all()
    valor = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "detalle"],
                name="unique_detalle_por_producto"
            )
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.detalle.nombre}: {self.valor}"        

    def clean(self):
        if self.detalle.categoria != self.producto.categoria:
            raise ValidationError(
                "El detalle no pertenece a la categoría del producto."
            )