from django.urls import path
from . import views

app_name = 'carro' # <a href = "{% url 'carro:agregar_producto' producto.id %}"> agregar </a>
urlpatterns = [
    path('cesta/', views.cesta, name='cesta'),

    path('agregar_producto/<int:producto_id>/', views.agregar_producto, name='agregar_producto'),
    path('eliminar_producto/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
    path('restar_producto/<int:producto_id>/', views.restar_producto, name='restar_producto'),
    path('limpiar_carro/', views.limpiar_carro, name='limpiar_carro'),  
]