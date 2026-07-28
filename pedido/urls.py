from django.urls import path
from . import views

urlpatterns = [
    path('pedido/', views.procesar_pedido, name='procesar_pedido'),
]