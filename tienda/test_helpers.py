from tienda.models import (
    Marca, Modelo, Sistema, Categoria, ProductoMarca, Producto,
)
from decimal import Decimal

def crear_catalogo_base(sufijo=''):
    """Crea la cadena mínima de FKs para un Producto."""
    marca = Marca.objects.create(nombre=f'Marca{sufijo}')
    modelo = Modelo.objects.create(nombre=f'Modelo{sufijo}', marca=marca)
    sistema = Sistema.objects.create(nombre=f'Sistema{sufijo}')
    categoria = Categoria.objects.create(nombre=f'Cat{sufijo}', sistema=sistema)
    producto_marca = ProductoMarca.objects.create(
        nombre=f'PM{sufijo}', sistema=sistema
    )
    return {
        'marca': marca,
        'modelo': modelo,
        'sistema': sistema,
        'categoria': categoria,
        'producto_marca': producto_marca,
    }


def crear_producto(sufijo='', precio=Decimal('25.00'), almacen=10, **kwargs):
    base = crear_catalogo_base(sufijo)
    return Producto.objects.create(
        nombre=kwargs.pop('nombre', f'Producto{sufijo}'),
        precio=precio,
        almacen=almacen,
        marca=base['marca'],
        modelo=base['modelo'],
        sistema=base['sistema'],
        categoria=base['categoria'],
        producto_marca=base['producto_marca'],
        **kwargs,
    )