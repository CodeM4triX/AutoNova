"""
URL configuration for Alpha project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
# ---> para archivos media importamos
from django.conf import settings
from django.conf.urls.static import static

from tienda import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('tienda.urls') ),
    path('', include('account.urls')),
    path('', include('carro.urls')),
    path('', include('pedido.urls')),

    # fILTER PRODUCTOS SEGUN MARCA Y MODELO
    path('filter_products/', views.filter_products, name='filter_products'),

    # SELECT Panel de administracion
    path('get_categorias/', views.get_categorias, name='get_categorias'),
    path('get_productoMarca/', views.get_productoMarca, name='get_productoMarca'),
    path('get_modelos/', views.get_modelos, name='get_modelos'),
    path("get_detalles/", views.get_detalles, name="get_detalles"),

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
