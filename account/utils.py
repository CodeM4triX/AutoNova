import unicodedata
from collections import OrderedDict
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Q
from django.utils.encoding import force_str
from django.utils.http import base36_to_int, int_to_base36, urlencode

from Alpha.utils import get_request_param, valid_email_or_none, import_callable
from account import app_settings, signals
from account.models import Login
from account.adapter import get_adapter
from core.exceptions import ImmediateHttpResponse

def assess_unique_email(email) -> Optional[bool]: # EVALUAR EMAIL UNICO
    #     ->         :   funcion retorna
    # Optional[bool] :  'Optional' palabra clave, el cual indica que el valor de retorno puede ser "None", ademas de un booleano ['True', 'False']
    """
    True -- email is unique
    False -- email is already in use
    None -- email is in use, but we should hide that using email verification.
    """
    if not filter_users_by_email(email): # si no hay usuarios_filtrados_por_email(email) en BBDD 
        return True
    elif not app_settings.PREVENT_ENUMERATION: # si primera condicion se cumple -> si no PREVENT_ENUMERATION habilitada
        return False # lo que significa que no se está previniendo la enumeración de emails. (indica que el email no es único y no se puede utilizar.)
    elif (app_settings.EMAIL_VERIFICATION == app_settings.EmailVerificationMethod.MANDATORY): # EMAIL_VERIFICATION == MANDATORY  y PREVENT_ENUMERATION activada
        assert app_settings.PREVENT_ENUMERATION
        return None
    elif app_settings.PREVENT_ENUMERATION == "strict": # significa que se permiten múltiples cuentas con el mismo correo electrónico sin verificar
        return True  # indica que el correo electrónico es único y puede utilizarse para registrar un nuevo usuario.
    else:
        assert app_settings.PREVENT_ENUMERATION is True
        return False
        
def cleanup_email_addresses(request, addresses): # LIMPIAR DIRECCION EMAIL
    from .models import EmailAddress

    adapter = get_adapter()
    e2a = OrderedDict()  # maps email to EmailAddress   ---> def OrderedDict() -> crea un diccionario ordenado
    primary_addresses = [] # lista para direcciones email primarias
    verified_addresses = [] # lista para direcciones email verificadas
    primary_verified_addresses = [] # lista para direcciones email primarias y verificadas
    for address in addresses: # address = [user1@gmail.com, user2@gmail.com,user3@gmail.com]
        email = valid_email_or_none(address.email) # email -> obtiene_email_valido_o_None -> de -> (address.email)
        if not email: # si email es None. la iteracion continua con la proxima direccion email --> 'address'
            continue
        if (app_settings.UNIQUE_EMAIL and app_settings.PREVENT_ENUMERATION != "strict" and EmailAddress.objects.lookup([email])): # True si existe en BBDD
            continue
        if (app_settings.UNIQUE_EMAIL and app_settings.PREVENT_ENUMERATION == "strict" and address.verified and EmailAddress.objects.is_verified(email)):
            continue
        a = e2a.get(email.lower()) # e2a={'email.lower()'} ------> obtener el valor de la clave 'email.lower()' del diccionario e2a
        if a: # si a ya esta en e2a={}
            a.primary = a.primary or address.primary  # EXPRESION a.primary  O  address.primary  es True -> entonces a.primary se actualiza a True
            a.verified = a.verified or address.verified
        else:
            a = address  # a = user1@gmail.com
            a.verified = a.verified or adapter.is_email_verified(request, a.email) # a.verified or is_email_verified()
            e2a[email.lower()] = a # e2a = {'email.lower()': user1@gmail.com}
        if a.primary: 
            primary_addresses.append(a) # primary_addresses = [a]
            if a.verified:
                primary_verified_addresses.append(a) # primary_verified_address = [a]
        if a.verified:
            verified_addresses.append(a) # verified_addresses = [a]
    if primary_verified_addresses: # primary_verified_address = [a]
        primary_address = primary_verified_addresses[0] # variable  ->    primary_address = a
    elif verified_addresses: # verified_addresses = [a]
        primary_address = verified_addresses[0]  # variable  ->    primary_address = a
    elif primary_addresses: # primary_addresses = [a]
        primary_address = primary_addresses[0]   # variable  ->    primary_address = a
    elif e2a: # e2a = {key:b} -> si hay direcciones email en el diccionario e2a = {}
        primary_address = list(e2a.values())[0]  # primari_address = b
    else:
        primary_address = None
    for a in e2a.values(): # para cada value en e2a = {key:values}
        a.primary = primary_address.email.lower() == a.email.lower()  # dirección email 'a.email'   ==    'primary_address.email'  dirección email principal  
    return list(e2a.values()), primary_address # list = [value1,value2] , primari_address -> direccion email principal

def complete_signup(request, user, email_verification, success_url, signal_kwargs=None): # COMPLETAR REGISTRO
    if signal_kwargs is None:
        signal_kwargs = {}
    signals.user_signed_up.send(sender=user.__class__, request=request, user=user, **signal_kwargs)
    return perform_login(
        request,
        user,
        email_verification=email_verification,
        signup=True,
        redirect_url=success_url,
        signal_kwargs=signal_kwargs,
    )

def filter_users_by_username(*username): # FILTRAR USUARIO POR USERNAME
    if app_settings.PRESERVE_USERNAME_CASING:
        qlist = [
            Q(**{app_settings.USER_MODEL_USERNAME_FIELD + "__iexact": u}) # Q(**{'campo':'value'})
            for u in username # [username1,username2]
        ]
        q = qlist[0] # q=Q1
        for q2 in qlist[1:]:  # qlist = [Q2,Q3..]
            q = q | q2
        ret = get_user_model()._default_manager.filter(q) # var ret = [obj1,obj2....]
    else:
        ret = get_user_model()._default_manager.filter(**{app_settings.USER_MODEL_USERNAME_FIELD + "__in": [u.lower() for u in username]})
    return ret # return conjunto de usuarios filtrados


def filter_users_by_email(email, is_active=None, prefer_verified=False): # FILTRAR USERS POR EMAIL
    from .models import EmailAddress

    User = get_user_model()
    mails = EmailAddress.objects.filter(email__iexact=email).prefetch_related("user")
    mails = list(mails) # emails = [mail1,mail2...]
    is_verified = False
    if prefer_verified:
        verified_mails = list(filter(lambda e: e.verified, mails))   # for e in mails: if e.verified:
        if verified_mails: # verified_mails = [......]
            mails = verified_mails 
            is_verified = True
    users = []
    for e in mails:
        if _unicode_ci_compare(e.email, email):
            users.append(e.user)  
    if app_settings.USER_MODEL_EMAIL_FIELD and not is_verified:
        q_dict = {app_settings.USER_MODEL_EMAIL_FIELD + "__iexact": email} # q_dict = {field_email:email}
        user_qs = User.objects.filter(**q_dict) # filter(field=email)
        for user in user_qs.iterator(): # iterator() -> permite recorrer los resultados del queryset uno por uno.
            user_email = getattr(user, app_settings.USER_MODEL_EMAIL_FIELD) # obtener_atributo(objeto, attr)
            if _unicode_ci_compare(user_email, email):
                users.append(user)
    if is_active is not None:
        users = [u for u in set(users) if u.is_active == is_active]
    return list(set(users)) # list({1, 2, 3, 4})     --->  [1, 2, 3, 4]

def get_login_redirect_url(request, url=None, redirect_field_name="next", signup=False): # OBTENER URL DE REDIRECCIONAMIENTO DE INICIO DE SESION
    ret = url
    if url and callable(url): # invocable-> si url es una funcion
        ret = url() # se llama a la funcion url()
    if not ret: 
        ret = get_next_redirect_url(request, redirect_field_name=redirect_field_name) 
    if not ret:
        if signup:
            ret = get_adapter().get_signup_redirect_url(request) # obtener url de redirecciones de registro
        else:
            ret = get_adapter().get_login_redirect_url(request) # obtener url de redirecciones de inicio sesion
    return ret

def get_next_redirect_url(request, redirect_field_name="next"): # OBTENER SIGUIENTE URL DE REDIRECCIONES
    redirect_to = get_request_param(request, redirect_field_name) 
    if not get_adapter().is_safe_url(redirect_to): # si url no es seguro
        redirect_to = None
    return redirect_to

def has_verified_email(user, email=None): # TIENE EMAIL VERIFICADO
    from .models import EmailAddress
    emailaddress = None
    if email:
        ret = False
        try:
            emailaddress = EmailAddress.objects.get_for_user(user, email) # obtener objeto asociado al user y email del modelo 'EmailAddress'
            ret = emailaddress.verified # objeto.atributo
        except EmailAddress.DoesNotExist:
            pass
    else:
        ret = EmailAddress.objects.filter(user=user, verified=True).exists() # filtrar objeto del modelo con estos parametros (user=user, verified=True)
    return ret

def passthrough_next_redirect_url(request, url, redirect_field_name): # APROBAR A TRAVEZ DEL SIGUIENTE URL DE REDIRECCIONES
    # TODO: Handle this case properly
    assert url.find("?") < 0  # find() devuelve la posición de la primera aparición de "?" en la cadena 'url' o -1 si no se encuentra
    next_url = get_next_redirect_url(request, redirect_field_name)
    if next_url: 
        # url -> url orginal a la que se le van a agregar parametros de consulta 
        # ?   -> Se utiliza para separar la URL base de los parámetros de consulta.
        # urlencode() -> toma un diccionario y lo convierte en una cadena de consulta codificada
        url = url + "?" + urlencode({redirect_field_name: next_url}) # construccion de una nueva URL
    return url

def perform_login(request, user, email_verification, redirect_url=None, signal_kwargs=None, signup=False, email=None,):
    login = Login(
        user=user,
        email_verification=email_verification,
        redirect_url=redirect_url,
        signal_kwargs=signal_kwargs,
        signup=signup,
        email=email,
    )
    return _perform_login(request, login)

def _perform_login(request, login): # REALIZAR INICIO DE SESION
    adapter = get_adapter()
    hook_kwargs = _get_login_hook_kwargs(login) # obtener kwargs para ganchos de inicio de sesion
    response = adapter.pre_login(request, login.user, **hook_kwargs)
    if response:
        return response
    return resume_login(request, login)


def _get_login_hook_kwargs(login): # OBTENER KWARGS DE ENLACE DE INICIO DE SESION
    return dict(
        email_verification=login.email_verification,
        redirect_url=login.redirect_url,
        signal_kwargs=login.signal_kwargs,
        signup=login.signup,
        email=login.email,
    )


def resume_login(request, login): # REANUDAR INICIO DE SESION
    from account.stages import LoginStageController

    adapter = get_adapter() # obtener el adaptador
    ctrl = LoginStageController(request, login) # objeto ctrl de class LoginStageController()   -> controlador de escenario de inicio de sesion
    try:
        response = ctrl.handle() # objeto.metodo()   ->  manejar
        if response:
            return response
        adapter.login(request, login.user)
        hook_kwargs = _get_login_hook_kwargs(login) # obtener keargs para ganchos de inicio de sesion
        response = adapter.post_login(request, login.user, **hook_kwargs)
        if response:
            return response
    except ImmediateHttpResponse as e:
        response = e.response
    return response

def send_email_confirmation(request, user, signup=False, email=None): # ENVIAR EMAIL DE CONFIRMACION
    from .models import EmailAddress

    adapter = get_adapter()
    email_address = None
    if not email:
        email = user_email(user) # def user_email(user, *args, commit=False): # EMAIL DE USUARIO -----> obtener email de usuario
    if not email:
        email_address = (EmailAddress.objects.filter(user=user).order_by("verified", "pk").first()) # obtener el primer objeto -> de -> BBDD
        if email_address:
            email = email_address.emailm # se obtiene el email del objeto -> email_address
    if email:
        if email_address is None:
            try:
                #pdb.set_trace()
                email_address = EmailAddress.objects.get_for_user(user, email)
            except EmailAddress.DoesNotExist:
                pass       
        if email_address is not None: # Verifica si se encontró una instancia de EmailAddress.
            if not email_address.verified: # verifica si objeto esta verificado 
                send_email = adapter.should_send_confirmation_mail(request, email_address, signup) # deberia_enviar_email_confirmacion() return True
                if send_email: # True
                    #pdb.set_trace()
                    email_address.send_confirmation(request, signup=signup) # llama al metodo en la instancia de EmailAddress para send email de confirmation
            else:
                send_email = False
        else: 
            send_email = True # enviar email de confirmacion
            email_address = EmailAddress.objects.add_email(request, user, email, signup=signup, confirm=True) # se crea una instancia
            assert email_address
        if send_email: # True
            adapter.add_message(
                request,
                messages.INFO,
                "account/messages/email_confirmation_sent.txt",
                {"email": email, "login": not signup, "signup": signup},
            )
    if signup: # verifica si user esta registrandose
        adapter.stash_user(request, user_pk_to_url_str(user)) # almacenar temporalmente la información del usuario

def setup_user_email(request, user, addresses): # CONFIGURACION EMAIL DE USUARIO
    from .models import EmailAddress

    assert not EmailAddress.objects.filter(user=user).exists() # assert expresión, mensaje_de_error
    priority_addresses = []
    adapter = get_adapter()
    stashed_email = adapter.unstash_verified_email(request) # escondido_email = user1@gmail.com
    if stashed_email: # si hay email_escondido
        priority_addresses.append(EmailAddress(user=user, email=stashed_email, primary=True, verified=True)) # priority_addresses = [user1@gmail.com]
    email = user_email(user) # obtener email asociado al user 
    if email: # emailAsociadoUser@gmail.com
        priority_addresses.append(EmailAddress(user=user, email=email, primary=True, verified=False)) # priority_addresses = [emailAsociadoUser@gmail.com]
    addresses, primary = cleanup_email_addresses(request, priority_addresses + addresses) # limpiar_email_direccion
    for a in addresses:
        a.user = user # asignar 'user' a cada direccion email 'a'
        a.save() # guardar en BBDD
    EmailAddress.objects.fill_cache_for_user(user, addresses)              # llenar_cache(de direcciones email)_para_user
    if primary and email and email.lower() != primary.email.lower():
        user_email(user, primary.email)
        user.save() # Después de actualizar email del usuario, se guarda el usuario en BBDD para aplicar los cambios realizados.
    return primary # return direccion_principal

def sync_user_email_addresses(user): # SINCRONIZAR DIRECCION EMAIL CON USUARIO
    from .models import EmailAddress
    email = user_email(user)
    if (email and not EmailAddress.objects.filter(user=user, email__iexact=email).exists()):
        EmailAddress.objects.get_or_create(user=user, email=email, defaults={"primary": False, "verified": False})

def stash_login(request, login): # INICIO DE SESION OCULTO
    request.session["account_login"] = login.serialize()
    request._account_login_accessed = True

def unstash_login(request, peek=False): # INICIO DE SESION DESOCULTO
    login = None
    if peek:
        data = request.session.get("account_login") # obtener datos de inicio de sesion de la clave 'account_login'  request.session = {key:value}
    else:
        data = request.session.pop("account_login", None) # elimina y obtiene los datos de inicio de sesion con la clave 'account_login'
    if data is not None:
        try:
            login = Login.deserialize(data) # class.metodo(data)
            request._account_login_accessed = True # establecer atributo _account_login_accessed en el objeto request para indicar que se ha accedido al Login
        except ValueError:
            pass
    return login

def user_email(user, *args, commit=False):
    return user_field(user, app_settings.USER_MODEL_EMAIL_FIELD, *args, commit=commit)

def user_username(user, *args, commit=False):
    if args and not app_settings.PRESERVE_USERNAME_CASING and args[0]:
        args = [args[0].lower()]
    return user_field(user, app_settings.USER_MODEL_USERNAME_FIELD, *args)

def user_field(user, field, *args, commit=False):
    if not field:
        return
    User = get_user_model()
    try:
        field_meta = User._meta.get_field(field)
        max_length = field_meta.max_length
    except FieldDoesNotExist:
        if not hasattr(user, field):
            return
        max_length = None
    if args:
        v = args[0]
        if v:
            v = v[0:max_length]
        setattr(user, field, v) # establecer dinamicamente el valor de un campo en un objeto usuario
        if commit:
            user.save(update_fields=[field])
    else:
        return getattr(user,field)

def user_pk_to_url_str(user): # CADENA DE USER PRIMARY PARA URL 
    User = get_user_model()
    pk_field_class = type(User._meta.pk) # obtener 'type' -> User.atributo.pk
    if issubclass(pk_field_class, models.UUIDField): # es sub clase, la clase -> (pk_field_class) de la clase_or_tupla -> (models.UUIDField)             
        if isinstance(user.pk, str): # comprueba si el valor de la clave primaria (user.pk) es una cadena (str) ------> isinstance(objeto, class_or_tupla)
            return user.pk 
        return user.pk.hex # hex() función que se utiliza para convertir números enteros en representaciones hexadecimales
    elif issubclass(pk_field_class, models.IntegerField): # issubclass(claseB, ClaseA)
        return int_to_base36(int(user.pk))
    return str(user.pk) # Finalmente, si el tipo de campo de clave primaria no es ni UUIDField ni IntegerField, return cadena del valor -> str(user.pk)

def url_str_to_user_pk(pk_str): # CADENA DE URL PARA USER PRIMARY KEY
    User = get_user_model()
    remote_field = getattr(User._meta.pk, "remote_field", None) # getattr(objeto, atributo)
    if remote_field and getattr(remote_field, "to", None): # get(objeto, 'to', None)
        pk_field = User._meta.pk.remote_field.to._meta.pk # to._meta.pk -> Este campo de clave primaria se asigna a la variable pk_field.
    else:
        pk_field = User._meta.pk # campo "pk" del modelo de usuario (User)
    pk_field_class = type(pk_field)
    if issubclass(pk_field_class, models.IntegerField): # issubclass(claseA, claseB)
        pk = base36_to_int(pk_str)
        pk = pk_field.to_python(pk) # invocar al método to_python() del campo de clave primaria (pk_field) para convertir este valor al tipo de dato adecuado
    else:
        pk = pk_field.to_python(pk_str) # invocar to_python() del campo de clave primaria (pk_field) para convertir pk_str al tipo de dato adecuado.
    return pk

def default_user_display(user): # MOSTRAR USUARIO POR DEFECTO
    if app_settings.USER_MODEL_USERNAME_FIELD:
        return getattr(user, app_settings.USER_MODEL_USERNAME_FIELD) # obtener atributo (objeto, atributo)
    else:
        return force_str(user) # django.utils.encoding import force_str

def _unicode_ci_compare(s1, s2): # UNICODE CI COMPARAR
    # casefold() -> convierte el texto normalizado en minusculas
    norm_s1 = unicodedata.normalize("NFKC", s1).casefold() # normalizar('forma_normalizacion', texto_identificador)
    norm_s2 = unicodedata.normalize("NFKC", s2).casefold()
    return norm_s1 == norm_s2

_user_display_callable = None # usuario invocable mostrar
def user_display(user): # MOSTRAR USUARIO
    global _user_display_callable # declaracion de una variable global
    if not _user_display_callable:
        f = getattr(settings, "ACCOUNT_USER_DISPLAY", default_user_display) # obtner el valor de ->  ACCOUNT_USER_DISPLAY   -> del modulo --> settings
        _user_display_callable = import_callable(f) # import_callable() -> devuelve una función basada en el valor de f.
    return _user_display_callable(user)  # se llama a esa funcion
