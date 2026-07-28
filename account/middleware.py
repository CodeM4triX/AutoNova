from django.conf import settings
from django.utils.decorators import sync_and_async_middleware

from asgiref.sync import iscoroutinefunction

from core import context
from core.exceptions import ImmediateHttpResponse

@sync_and_async_middleware
def AccountMiddleware(get_response):
    if iscoroutinefunction(get_response):
        async def middleware(request): 
            # La sentencia with en Python se utiliza para trabajar con objetos que soportan el protocolo de contexto.
            """
            with se encarga de que, al finalizar el bloque de código dentro de with, se realice alguna operación de limpieza o liberación de recursos.
            En este caso, podría ser la liberación de recursos asociados con el contexto de solicitud.
            """
            with context.request_context(request):
            
                """
                Cuando se usa await dentro de una función async, indica que la función debe pausarse
                hasta que la operación asincrónica que sigue a await se complete.
                Mientras espera, la ejecución se puede pasar a otras partes del programa, permitiendo que otras tareas continúen ejecutándose en el mismo hilo
                """
                
                try:
                    # await -> se utiliza para esperar el resultado de una operación asincrónica sin bloquear todo el hilo de ejecución
                    response = await get_response(request) # get_response() -> funcion pasado como parametro
                    _remove_dangling_login(request, response) # eliminar inicio de sesion colgado
                    return response
                except ImmediateHttpResponse as e: 
                    return e.response

    else:
        
        def middleware(request):
            #pdb.set_trace()
            with context.request_context(request): # se crea un contexto de solicitud para la solicitud actual.
                try:
                    response = get_response(request)
                    _remove_dangling_login(request, response)
                    return response
                except ImmediateHttpResponse as e:
                    return e.response
    
    # se devuelve la función middleware definida, que será utilizada como parte del middleware en el caso de que get_response no sea una función asíncrona.
    #pdb.set_trace()
    return middleware


def _remove_dangling_login(request, response): # ELIMINAR INICIO DE SESION COLGADO
    content_type = response.headers.get("content-type") # obtener "content-type", que indica el tipo de datos que se devuelve en la respuesta.
    if content_type: # si se ha encontrado un tipo de contenido
    
        # content_type = "text/html; charset=utf-8"
        # content_type.partition(";")[0]    =>    text/html

        content_type = content_type.partition(";")[0] # se divide la cadena utilizando el carácter ";" como delimitador y se obtiene la primera parte 
        
    if content_type and content_type != "text/html":
        return
    
    # Si la ruta de la solicitud comienza con la URL estática configurada (settings.STATIC_URL)      or
    if request.path.startswith(settings.STATIC_URL) or request.path in ["/favicon.ico", "/robots.txt", "/humans.txt",]:
        return
        
    # response.status_code -> status_code representa el código de estado HTTP devuelto, como 200 para éxito, 404 para no encontrado, etc.
    # // -> operador de división entera en Python. Divide el operando izquierdo por el operando derecho y devuelve el cociente como un número entero
    if response.status_code // 100 != 2: # 200//100 != 2
        return
    # if not False -> True
    if not getattr(request, "_account_login_accessed", False):
        if "account_login" in request.session: # si hay una clave "account_login" en la sesión
            request.session.pop("account_login") # se extrae y elimina esta clave de la sesión.
