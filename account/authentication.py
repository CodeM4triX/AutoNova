import time

# CONSTANTE
# AUTHENTICATION_METHODS_SESSION_KEY que representa la clave en la sesión del usuario donde se almacenarán los métodos de autenticación registrados
AUTHENTICATION_METHODS_SESSION_KEY = "account_authentication_methods"
def record_authentication(request, method, **extra_data): # REGISTRO DE AUTENTICACION
    """
    Example data::

        {'method': 'password',
         'at': 1701423602.7184925,
         'username': 'john.doe'}

        {'method': 'socialaccount',
         'at': 1701423567.6368647,
         'provider': 'amazon',
         'uid': 'amzn1.account.K2LI23KL2LK2'}

        {'method': 'mfa',
         'at': 1701423602.6392953,
         'id': 1,
         'type': 'totp'}

    """
    methods = request.session.get(AUTHENTICATION_METHODS_SESSION_KEY, [])
    data = {"method": method, "at": time.time(), **extra_data}
    methods.append(data) # methods = [{'method':method, 'at':time.time(), **extra_data}]
    request.session[AUTHENTICATION_METHODS_SESSION_KEY] = methods # request.session = {'AUTHENTICATION_METHODS_SESSION_KEY':methods}
