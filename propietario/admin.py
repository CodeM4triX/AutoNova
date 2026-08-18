from django.contrib import admin

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from .models import PropietarioInfo

@admin.register(PropietarioInfo)
class AdministradorInfoAdmin(admin.ModelAdmin):
    # Evita que el usuario pueda añadir más registros desde el botón superior
    def has_add_permission(self, request):
        if PropietarioInfo.objects.exists():
            return False
        return True

    # Evita que se puedan borrar los datos, ya que el sistema los necesita siempre
    def has_delete_permission(self, request, obj=None):
        return False

    # Redirección automática: si entra a la lista, va directo a editar el único registro existente
    def changelist_view(self, request, extra_context=None):
        obj = PropietarioInfo.objects.first()
        if obj:
            # CÓDIGO CORREGIDO: Usa el nombre real de tu app y de tu modelo (en minúsculas)
            return redirect(reverse('admin:propietario_propietarioinfo_change', args=[obj.pk]))
        return super().changelist_view(request, extra_context)

