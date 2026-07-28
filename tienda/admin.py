from django.contrib import admin
from .models import (
    Marca,
    Modelo,
    Sistema,
    Categoria,
    ProductoMarca,
    Producto,
    ImagenProducto,
    DetalleCategoria,
    ValorDetalleProducto
)

class ImagenProductoInline(admin.TabularInline):
    model = ImagenProducto
    extra = 3
    max_num = 3

class ValorDetalleProductoInline(admin.TabularInline):
    model = ValorDetalleProducto
    extra = 1

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'marca', 'modelo', 'almacen')

    inlines = [
        ImagenProductoInline,
        ValorDetalleProductoInline,
    ]

    class Media:
        js = [
            "js/categoria_select.js",
            "js/modelo_select.js",
            "js/detalle_select.js",
        ]

@admin.register(ImagenProducto)
class ImagenProductoAdmin(admin.ModelAdmin):
    list_display = ("producto", "imagen")

@admin.register(DetalleCategoria)
class DetalleCategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria")
    list_filter = ("categoria",)
    search_fields = ("nombre",)

@admin.register(ValorDetalleProducto)
class ValorDetalleProductoAdmin(admin.ModelAdmin):
    list_display = ("producto", "detalle", "valor")
    list_filter = ("detalle__categoria",)
    search_fields = ("producto__nombre", "detalle__nombre")

admin.site.register(Marca)
admin.site.register(Modelo)
admin.site.register(Sistema)
admin.site.register(Categoria)
admin.site.register(ProductoMarca)
