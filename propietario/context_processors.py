from .models import PropietarioInfo

def info_propietario_global(request):
    # Retorna un diccionario con los datos del administrador
    return {
        'global_propietario': PropietarioInfo.objects.first()
    }
