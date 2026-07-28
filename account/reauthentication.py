import time

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.urls import resolve, reverse
from django.utils.http import urlencode

from Alpha.utils import import_callable
from account import app_settings
from account.adapter import get_adapter
from account.utils import get_next_redirect_url
from core.internal.http import deserialize_request, serialize_request

# CONSTANTE 
STATE_SESSION_KEY = "account_reauthentication_state" # clave para acceder al estado de reautenticación en la sesión del usuario.
AUTHENTICATED_AT_SESSION_KEY = "account_authenticated_at" # clave para acceder al momento de autenticación en la sesión del usuario.

def suspend_request(request, redirect_to): # SUSPENDER SOLICITUD
    path = request.get_full_path() # obtener la ruta completa de la solicitud actual   -> "/mypage/?param1=value1&param2=value2"
    if request.method == "POST":
        request.session[STATE_SESSION_KEY] = {"request": serialize_request(request)} # from allauth.core.internal.http import serialize_request()
    return HttpResponseRedirect(redirect_to + "?" + urlencode({REDIRECT_FIELD_NAME: path}))

def resume_request(request): # REANUDAR SOLICITUD
    state = request.session.pop(STATE_SESSION_KEY, None) # extraer y eliminar el estado de reautenticación de la sesión del usuario utilizando la clave
    if state and "callback" in state:         # si se encontro un estado, y si contiene una clave 'callback'
        callback = import_callable(state["callback"]) #importar y devolver un objeto de función basado en el nombre de la función proporcionada        
        return callback(request, state["state"]) # Llama al callback con el objeto de solicitud request y el estado almacenado en la sesión.
    url = get_next_redirect_url(request, REDIRECT_FIELD_NAME) # Obtiene la URL a la que se redirigirá al usuario después de reanudar la solicitud
    if not url:
        return None
    if state and "request" in state: # Verifica si hay un estado y si contiene una solicitud suspendida.
        suspended_request = deserialize_request(state["request"], request) # Deserializa la solicitud suspendida a partir del estado y la solicitud actual.
        if suspended_request.path == url: # si la ruta de la solicitud suspendida es igual a la URL de redirección obtenida.
            resolved = resolve(suspended_request.path) # Resuelve la ruta de la solicitud suspendida para encontrar la vista asociada a esa ruta.
            return resolved.func(suspended_request, *resolved.args, **resolved.kwargs)
    return HttpResponseRedirect(url) # Redirige al usuario a la URL de redirección obtenida

def record_authentication(request, user): # REGISTRO DE AUTENTICACION
    request.session[AUTHENTICATED_AT_SESSION_KEY] = time.time()

def reauthenticate_then_callback(request, serialize_state, callback): # REAUTENTICAR ENTONCES VOLVER A LLAMAR
    if did_recently_authenticate(request): # si usuario se autentico recientemente
        return None
    request.session[STATE_SESSION_KEY] = {"state": serialize_state(request), "callback": callback} # request.session = {'key':{'state':value}, }
    return HttpResponseRedirect(reverse("account_reauthenticate")) # Redirige al usuario a la página de reautenticación.

def did_recently_authenticate(request): # SE AUTENTICO RECIENTEMENTE
    if request.user.is_anonymous: # si usuario no se ha registrado
        return False 
    if not get_adapter().get_reauthentication_methods(request.user):
        return True
    authenticated_at = request.session.get(AUTHENTICATED_AT_SESSION_KEY)
    if not authenticated_at: # si no hay una marca de tiempo de autenticación en la sesión
        return False # False, indica que el usuario no ha sido autenticado recientemente.
    return time.time() - authenticated_at < app_settings.REAUTHENTICATION_TIMEOUT # return True si es menor al fuera de tiempo (tiempo de espera)
