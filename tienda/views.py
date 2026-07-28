from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import never_cache
from django.http import JsonResponse

from .models import (
    Producto,
    Sistema,
    Marca,
    Modelo,
    Categoria,
    ProductoMarca,
    DetalleCategoria
)
from .pagination import paginar_productos
from django.db.models import Prefetch
from .models import ValorDetalleProducto

@never_cache
def tienda(request):
    sistemas = Sistema.objects.all()
    marcas = Marca.objects.all()
    return render(request, 'tienda/tienda.html', {
        'sistemas': sistemas,
        'marcas': marcas,
    })


@never_cache
def categoria(request, categoria_id):
    sistemas = Sistema.objects.all()
    marcas = Marca.objects.all()
    categoria_obj = get_object_or_404(Categoria, id=categoria_id)
    """
    productos_qs = Producto.objects.filter(
        categoria=categoria_obj
    ).select_related(
        'marca', 'modelo', 'producto_marca'
    ).order_by('nombre')
    """
    productos_qs = Producto.objects.filter(
        categoria=categoria_obj
    ).select_related(
        'marca',
        'modelo',
        'producto_marca'
    ).prefetch_related(
        Prefetch(
            "detalles",
            queryset=ValorDetalleProducto.objects.select_related("detalle")
        )
    ).order_by("nombre")

    productos = paginar_productos(request, productos_qs)

    return render(request, 'tienda/categoria.html', {
        'sistemas': sistemas,
        'marcas': marcas,
        'categoria': categoria_obj,
        'productos': productos,
    })


@never_cache
def filter_products(request):
    marca_id = request.GET.get('marca_id')
    modelo_id = request.GET.get('modelo_id')

    sistemas = Sistema.objects.all()
    marcas = Marca.objects.all()
    """
    productos_qs = Producto.objects.filter(
        marca_id=marca_id,
        modelo_id=modelo_id,
    ).select_related(
        'marca', 'modelo', 'producto_marca'
    ).order_by('nombre')
    """
    productos_qs = Producto.objects.filter(
        marca_id=marca_id,
        modelo_id=modelo_id,
    ).select_related(
        'marca',
        'modelo',
        'producto_marca'
    ).prefetch_related(
        Prefetch(
            "detalles",
            queryset=ValorDetalleProducto.objects.select_related("detalle")
        )
    ).order_by("nombre")

    productos = paginar_productos(request, productos_qs)

    pagination_query = ''
    if marca_id and modelo_id:
        pagination_query = f'marca_id={marca_id}&modelo_id={modelo_id}'

    return render(request, 'tienda/productos.html', {
        'sistemas': sistemas,
        'marcas': marcas,
        'productos': productos,
        'marca_id': marca_id,
        'modelo_id': modelo_id,
        'pagination_query': pagination_query,
    })

# Obtener las categorías de un sistema específico
def get_categorias(request):
    sistema_id = request.GET.get('sistema_id')
    categorias = Categoria.objects.filter(sistema_id=sistema_id).values('id', 'nombre')
    return JsonResponse(list(categorias), safe=False)

# Obtener las marcas de productos de un sistema específico
def get_productoMarca(request):
    sistema_id = request.GET.get('sistema_id')
    producto_marca = ProductoMarca.objects.filter(sistema_id=sistema_id).values('id', 'nombre')
    return JsonResponse(list(producto_marca), safe=False)

# Obtener los modelos de una marca específica
def get_modelos(request):
    marca_id = request.GET.get('marca_id')

    modelos = Modelo.objects.filter(
        marca_id=marca_id
    ).order_by(
        'nombre',
        'generacion'
    ).values(
        'id',
        'nombre',
        'generacion',
        'chasis',
        'anios_produccion'
    )
    return JsonResponse(list(modelos), safe=False)

# Obtener los detalles de una categoría específica
def get_detalles(request):
    categoria_id = request.GET.get("categoria_id")

    detalles = DetalleCategoria.objects.filter(
        categoria_id=categoria_id
    ).order_by("nombre").values(
        "id",
        "nombre"
    )

    return JsonResponse(list(detalles), safe=False)