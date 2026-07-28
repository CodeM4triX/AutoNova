import html
import json
import warnings
from datetime import timedelta
from urllib.parse import urlparse

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_backends,
    get_user_model,
    login as django_login,
    logout as django_logout,
)
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.password_validation import validate_password
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import FieldDoesNotExist
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import resolve_url
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.encoding import force_str
from django.utils.translation import gettext_lazy as _

from account import signals
from account.app_settings import (AuthenticationMethod, EmailVerificationMethod,)
from core import context, ratelimit
from Alpha.utils import (build_absolute_uri, generate_unique_username, import_attribute,)
from . import app_settings

class DefaultAccountAdapter(object):
    error_messages = {
        "enter_current_password": _("please type current password"),
        "incorrect_password": _("Incorrect_password"),
        "password_min_length": _("Password must be a minium of {0} characters"),
        "unknown_email": _("The email address is not assigned to any user account")
    }
    def __init__(self, request=None):
        self.request = context.request

    def add_message(self, request, level, message_template, message_context=None, extra_tags=""):
        if "django.contrib.messages" in settings.INSTALLED_APPS:
            try:
                if message_context is None:
                    message_context = {}
                escaped_message = render_to_string(message_template, message_context, context.request,).strip()
                if escaped_message:
                    message = html.unescape(escaped_message)
                    messages.add_message(request, level, message, extra_tags=extra_tags) # agregar_mensaje() -> message (el mensaje renderizado),
            except TemplateDoesNotExist: # si la plantilla no existe simplemente se pasa. no se agrega ningun mensaje
                pass

    def ajax_response(self, request, response, redirect_to=None, form=None, data=None):
        resp = {} 
        status = response.status_code # objeto.atributo
        if redirect_to: # si redirect_to != None
            status = 200
            resp["location"] = redirect_to # resp = {'location':redirect_to}
        if form: # si form != None
            if request.method == "POST": # request.method = POST
                if form.is_valid(): # True
                    status = 200
                else:
                    status = 400 # False
            else:
                status = 200
            resp["form"] = self.ajax_response_form(form) # resp = {'form':form_spec}
            if hasattr(response, "render"): # si tiene atributo 'render' el objeto 'response'
                response.render() # se llama al metodo render() -> para renderizar la respuest
                
            # content -> atributo, representa el cuerpo de la respuesta HTTP. Este cuerpo de respuesta puede ser de tipo bytes, 
            # decode('utf8') -> decodificar los bytes en una cadena de caracteres Unicode utilizando el esquema de codificación UTF-8.
            resp["html"] = response.content.decode("utf8")
        if data is not None:
            resp["data"] = data
        # modulo.dumps(diccionario) ->  la funcion dumps(), convierte un diccionario en una cadena JSON
        # HttpResponse                         -> crea un objeto 'HttpResponse'
        # json.dumps(resp)                     -> cadena de JSON (cuerpo de la respuesta)
        # status=status                        -> status_code de la respuesta 
        # content_type = "application/json"    -> tipo_contenido: se establece en "application/json" para indicar que el contenido de la respuesta es JSON.
        return HttpResponse(json.dumps(resp), status=status, content_type="application/json")

    def ajax_response_form(self, form):
        # ESPECIFICACIONE DE FORMULARIO
        form_spec = {
            "fields": {},
            "field_order": [],
            "errors": form.non_field_errors(),
        }
        for field in form: 
            # ESPECIFICACIONES DE CAMPO          
            field_spec = {
                "label": force_str(field.label), # etiqueta del campo. convertido a una cadena
                "value": field.value(),          # valor actual del campo
                "help_text": force_str(field.help_text),   # texto de ayuda del campo
                "errors": [force_str(e) for e in field.errors],   # errores asociados al campo
                "widget": {"attrs": {k: force_str(v) for k, v in field.field.widget.attrs.items()}},
            }
            form_spec["fields"][field.html_name] = field_spec # form_spec = {'field':{'field.html_name':field_spec}}
            form_spec["field_order"].append(field.html_name) # form_spec = {'field_order':[field.html_name]}
        return form_spec # ESPECIFICACIONES DEL FORMULARIO

    def pre_authenticate(self, request, **credentials):
        if app_settings.LOGIN_ATTEMPTS_LIMIT:
            cache_key = self._get_login_attempts_cache_key(request, **credentials)
            if not ratelimit.consume(
                request,
                action="login_failed",
                key=cache_key,
                amount=app_settings.LOGIN_ATTEMPTS_LIMIT,
                duration=app_settings.LOGIN_ATTEMPTS_TIMEOUT,
            ):
                raise forms.ValidationError(self.error_messages["too_many_login_attempts"]) # to_many(demasiados) demasiados intentos de inicio de sesion

    def authenticate(self, request, **credentials):
        from account.auth_backends import AuthenticationBackend

        self.pre_authenticate(request, **credentials)
        AuthenticationBackend.unstash_authenticated_user()
        user = authenticate(request, **credentials)
        alt_user = AuthenticationBackend.unstash_authenticated_user()
        user = user or alt_user
        if user and app_settings.LOGIN_ATTEMPTS_LIMIT: # si user != None and habilitada
            self._delete_login_attempts_cached_email(request, **credentials) # eliminar_intentos_inicio_sesion_de_email_de_cache()
        else:
            self.authentication_failed(request, **credentials)
        return user # Finalmente, el usuario autenticado (o None si no hay ningún usuario autenticado)

    def authentication_failed(self, request, **credentials):
        pass

    def reauthenticate(self, user, password):
        from account.models import EmailAddress
        from account.utils import user_username

        credentials = {"password": password}
        username = user_username(user)  # obtener el nombre de usuario del usuario dado
        if username:
            credentials["username"] = username # credentials = {'password':password, 'username':username}
        email = EmailAddress.objects.get_primary_email(user) # obtener direccion email principal del usuario
        if email:
            credentials["email"] = email   # credentials = {'password':password, 'username':username, 'email':email}
        reauth_user = self.authenticate(context.request, **credentials) # return objeto de usuario autenticado
        return reauth_user is not None and reauth_user.pk == user.pk # return True and reauth_user.pk

    def clean_username(self, username, shallow=False): # USERNAME LIMPIO  - VALIDACION DE NOMBRE DE USUARIO
        for validator in app_settings.USERNAME_VALIDATORS: # para cada def_validacion() en USERNAME_VALIDATORS
            validator(username) # y cada funcion la aplica al archivo "username"
        username_blacklist_lower = [ub.lower() for ub in app_settings.USERNAME_BLACKLIST]
        if username.lower() in username_blacklist_lower: # user in ['neo', 'user', 'adan']
            raise forms.ValidationError(self.error_messages["username_blacklisted"])
        if not shallow: # if not True -> False
            from .utils import filter_users_by_username
            if filter_users_by_username(username).exists():# if True  -> verifica si ya existe algun usuario con el "username" dado
                user_model = get_user_model()
                username_field = app_settings.USER_MODEL_USERNAME_FIELD # obtener el nombre del campo que almacena el nombre de usuario del modelo de usuario
                error_message = user_model._meta.get_field(username_field).error_messages.get("unique") # obtener el mensaje de error, si "username" duplicado
                if not error_message: # si no se ha definido un mensaje de error para un nombre de usuario duplicado
                    error_message = self.error_messages["username_taken"] # self.error_mesages = {'username_taken': message_error}
                raise forms.ValidationError(error_message, params={"model_name": user_model.__name__,"field_label": username_field,},)
        return username # Si la validación del nombre de usuario pasa todas las pruebas anteriores, se devuelve el nombre de usuario sin modificar.

    def clean_email(self, email): # VALIDAR EMAIL
        return email

    def clean_password(self, password, user=None): # VALIDAR CONTRASEÑA
        min_length = app_settings.PASSWORD_MIN_LENGTH # se obtiene la longitud minima para la contraseña
        if min_length and len(password) < min_length: # si longitud(password) < min_length
            raise forms.ValidationError(self.error_messages["password_min_length"].format(min_length)) 
        validate_password(password, user) # from django.contrib.auth.password_validation import validate_password
        return password

    def confirm_email(self, request, email_address):
        from account.models import EmailAddress

        from_email_address = (
            EmailAddress.objects.filter(user_id=email_address.user_id)
            .exclude(pk=email_address.pk)
            .first()
        )
        if not email_address.set_verified(commit=False): # si email_addres no se establece_verificado()
            return False
        email_address.set_as_primary(conditional=(not app_settings.CHANGE_EMAIL)) 
        email_address.save(update_fields=["verified", "primary"]) # guardar email actualizando los campos ['verified','primary']
        if app_settings.CHANGE_EMAIL:
            for instance in EmailAddress.objects.filter(user_id=email_address.user_id).exclude(pk=email_address.pk):
                instance.remove() # elimina todas las demás direcciones email asociadas al mismo usuario, excepto la que se está confirmando.
            signals.email_changed.send(
                sender=get_user_model(),
                request=request,
                user=email_address.user,
                from_email_address=from_email_address,
                to_email_address=email_address,
            )
        return True # Devuelve True para indicar que la confirmación del correo electrónico fue exitosa.

    def get_signup_redirect_url(self, request): # OBTENER URL DE REDIRECCIONES DE REGISTRO
        return resolve_url(app_settings.SIGNUP_REDIRECT_URL) # from django.shortcuts import resolve_url

    def get_login_redirect_url(self, request): # OBTENER URL DE REDIRECCIONES DE INICIO DE SESION
        assert request.user.is_authenticated # afirmar request.user ha iniciado sesion
        url = getattr(settings, "LOGIN_REDIRECT_URLNAME", None) # url = getattr(objeto, atributo, None)
        if url: # si url != None
            warnings.warn(
                "LOGIN_REDIRECT_URLNAME is deprecated, simply"
                " use LOGIN_REDIRECT_URL with a URL name",
                DeprecationWarning,
            )
        else:
            url = settings.LOGIN_REDIRECT_URL # obtener url de redirecciones de inicio de sesion
        return resolve_url(url) # funcion utilizada para convertir un nombre de URL, a una URL absoluta

    def get_login_stages(self): # OBTENER ETAPAS DE INICIO DE SESION
        ret = []
        """
        if allauth_app_settings.MFA_ENABLED: # MULTI FACTOR AUTENTICACION -> habilitada
            ret.append("allauth.mfa.stages.AuthenticateStage")
        """
        return ret # return lista con las etapas de inicio de sesion

    def get_logout_redirect_url(self, request): # OBTENER URL DE REDIRECCIONES DE CERRAR SESION
        return resolve_url(app_settings.LOGOUT_REDIRECT_URL)

    def get_email_confirmation_redirect_url(self, request): # OBTENER URL DE REDIRECCIONES DE CONFIRMACION DE EMAIL
        if request.user.is_authenticated: # si request.user ha iniciado sesion
            if app_settings.EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL: # url de redirecciones de confirmacion de email autenticado
                return app_settings.EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL # return url de redireccion
            else:
                return self.get_login_redirect_url(request) # obtener_url_redireciones_inicio_sesion()
        else:
            return app_settings.EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL # url de redirecciones para un usuario anonimo

    def get_password_change_redirect_url(self, request): #OBTENER URL DE REDIRECCIONES DE CAMBIO DE CONTRASEÑA
        return reverse("account_change_password") # reverse() -> obtiene URL absoluta asociada al nombre definido

    def _get_login_attempts_cache_key(self, request, **credentials): # OBTENER CLAVE DE CACHE DE INTENTOS DE INICIO DE SESION
        site = get_current_site(request) # El objeto "Site" representa el sitio web en el que se está realizando la solicitud.
        login = credentials.get("email", credentials.get("username", "")).lower()
        return "{site}:{login}".format(site=site.domain, login=login) # "site.domain:login"

    def _delete_login_attempts_cached_email(self, request, **credentials): # ELIMINAR INTENTOS DE INICIO DE SESION DE EMAIL EN CACHE
        if app_settings.LOGIN_ATTEMPTS_LIMIT:
            cache_key = self._get_login_attempts_cache_key(request, **credentials)
            ratelimit.clear(request, action="login_failed", key=cache_key) # modulo.function

    def is_ajax(self, request):
        # any() -> verifica si al menos una de las condiciones dentro de la lista es verdadera: entonces any() return True de lo contrario return False
        return any(
            [
                request.META.get("HTTP_X_REQUESTED_WITH") == "XMLHttpRequest",
                request.content_type == "application/json",
                request.META.get("HTTP_ACCEPT") == "application/json",
            ]
        )

    def is_email_verified(self, request, email): # EMAIL ES VERIFICADO
        ret = False
        verified_email = request.session.get("account_verified_email") # request.session = {'account_verified_email':value}    -> verified_email = value
        if verified_email:
            ret = verified_email.lower() == email.lower()
        return ret

    def is_open_for_signup(self, request):
        return True

    def is_safe_url(self, url): # ES URL SEGURA
        from django.utils.http import url_has_allowed_host_and_scheme

        allowed_hosts = {context.request.get_host()} | set(settings.ALLOWED_HOSTS) 
        if "*" in allowed_hosts: 
            parsed_host = urlparse(url).netloc # var host_analizado
            allowed_host = {parsed_host} if parsed_host else None # si parsed_host != None --> allowed_host = {parsed_host}
            return url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_host) 
        return url_has_allowed_host_and_scheme(url, allowed_hosts=allowed_hosts)

    def new_user(self, request):
        user = get_user_model()()
        return user

    def populate_username(self, request, user):
        from account.utils import user_email, user_username, user_field
        
        first_name = user_field(user, "first_name")
        last_name = user_field(user, "last_name")
        email = user_email(user)
        username = user_username(user)
        if app_settings.USER_MODEL_USERNAME_FIELD:
            user_username(user, username or self.generate_unique_username([first_name, last_name, email, username, "user"]))
    
    def generate_unique_username(self, txts, regex=None):
        return generate_unique_username(txts, regex)

    def save_user(self, request, user, form, commit=True):
        from account.utils import user_email, user_username, user_field

        data = form.cleaned_data
        first_name = data.get("first_name")
        last_name = data.get("last_name")
        email = data.get("email")
        username = data.get("username")
        user_email(user, email)
        user_username(user, username)
        if first_name:
            user_field(user, "first_name", first_name)
        if last_name:
            user_field(user, "last_name", last_name)
        if "password1" in data:
            user.set_password(data["password1"])
        else:
            user.set_unusable_password()
        self.populate_username(request, user)
        if commit:
            user.save()
        return user
    
    def set_password(self, user, password):
        user.set_password(password)
        user.save()

    def format_email_subject(self, subject):
        prefix = app_settings.EMAIL_SUBJECT_PREFIX
        if prefix is None:
            site = get_current_site(context.request)
            prefix = "[{name}]".format(name=site.name)
        return prefix + force_str(subject)

    def generate_emailconfirmation_key(self, email): # GENERAR CLAVE DE EMAIL DE CONFIRMACION
        key = get_random_string(64).lower() # obtener_cadena_aleatoria(64) -> de longitud 64. lower() -> convierte la cadena en minusculas
        return key # return la cadena aleatoria

    def get_client_ip(self, request): # OBTENER IP DEL CLIENTE
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for: # si HTTP_X_FORWARDED_FOR está presente en la solicitud "request"
            ip = x_forwarded_for.split(",")[0] # x_forwarded_for = []
        else: # si HTTP_X_FORWARDED_FOR no esta presente en la solicitud "request"
            ip = request.META.get("REMOTE_ADDR") # obtener la dirección IP remota (REMOTE_ADDR) directamente desde los metadatos (META) de la solicitud. 
        return ip # devuelve la dirección IP obtenida

    def get_from_email(self):
        return settings.DEFAULT_FROM_EMAIL
        #return settings.EMAIL_HOST_USER

    def pre_login(self, request, user, *, email_verification, signal_kwargs, email, signup, redirect_url):
        from .utils import has_verified_email, send_email_confirmation
        #pdb.set_trace()
        if not user.is_active:
            return self.respond_user_inactive(request, user) # return HttpResponseRedirect(reverse("account_inactive"))
        if email_verification == EmailVerificationMethod.NONE: # None == None
            pass
        elif email_verification == EmailVerificationMethod.OPTIONAL:  # Opcional == Opcional
            if not has_verified_email(user, email) and signup: # si no tiene_email_verificado()  y  registro(esta en proceso de registro)
                send_email_confirmation(request, user, signup=signup, email=email) # enviar_email_de_confirmacion()
        elif email_verification == EmailVerificationMethod.MANDATORY:  # Mandatory == Mandatory
            if not has_verified_email(user, email):
                send_email_confirmation(request, user, signup=signup, email=email)
                return self.respond_email_verification_sent(request, user) # informar_email_de_verificacion_enviado() -> informa al usuario

    def post_login(self, request, user, *, email_verification, signal_kwargs, email, signup, redirect_url):
        from .utils import get_login_redirect_url # obtener url de redirecciones despues de inicio de sesion
        
        response = HttpResponseRedirect(get_login_redirect_url(request, redirect_url, signup=signup))
        if signal_kwargs is None: # si signal_kwargs = None , se establece como un diccionario vacío
            signal_kwargs = {}
        signals.user_logged_in.send(
            sender=user.__class__,
            request=request,
            response=response,
            user=user,
            **signal_kwargs,
        )
        self.add_message(
            request,
            messages.SUCCESS,
            "account/messages/logged_in.txt",
            {"user": user},
        )
        return response # Se devuelve la respuesta de redirección, que redirigirá al usuario a la URL determinada después de iniciar sesión

    def login(self, request, user):
        from account.reauthentication import record_authentication

        if not hasattr(user, "backend"): # si no tiene atributo "backend", el objeto "user"
            from .auth_backends import AuthenticationBackend
            backends = get_backends() # Obtiene una lista de todos los backends de autenticación disponibles en el sistema.
            backend = None
            for b in backends: # para cada "backend" en backends=[]
                if isinstance(b, AuthenticationBackend): # si "b"(backend), es una instancia de "AuthenticationBackend"
                    backend = b
                    break # salir del bucle for
                elif not backend and hasattr(b, "get_user"): # tiene atributo "get_user" el "b"(backend)
                    backend = b
            backend_path = ".".join([backend.__module__, backend.__class__.__name__]) # ruta_backend = [__module__.className]
            user.backend = backend_path # Este paso es necesario para que Django sepa qué backend de autenticación utilizar para este usuario.
        django_login(request, user) # iniciar sesion
        record_authentication(request, user) # Registra la autenticación del usuario 

    def logout(self, request):
        django_logout(request)

    def respond_user_inactive(self, request, user): # RESPONDER USUARIO INACTIVO
        return HttpResponseRedirect(reverse("account_inactive")) # crea un objeto response

    def respond_email_verification_sent(self, request, user): # RESPONDER EMAIL DE VERIFICACION ENVIADO
        return HttpResponseRedirect(reverse("account_email_verification_sent"))

    def render_mail(self, template_prefix, email, context, headers=None):
        to = [email] if isinstance(email, str) else email
        #pdb.set_trace()
        subject = render_to_string("{0}_subject.txt".format(template_prefix), context)
        subject = "".join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)
        from_email = self.get_from_email()
        bodies = {}
        html_ext = app_settings.TEMPLATE_EXTENSION
        for ext in [html_ext, "txt"]:
            try:
                template_name = "{0}_message.{1}".format(template_prefix, ext)
                bodies[ext] = render_to_string(template_name, context, globals()["context"].request).strip()
            except TemplateDoesNotExist:
                if ext == "txt" and not bodies:
                    raise
        if "txt" in bodies:
            msg = EmailMultiAlternatives(subject, bodies["txt"], from_email, to , headers=headers)
            if html_ext in bodies:
                msg.attach_alternative(bodies[html_ext], "text/html")
        else:
            msg = EmailMessage(subject, bodies[html_ext], from_email, to, headers=headers)
            msg.content_subtype = "html"
        return msg

    def send_mail(self, template_prefix, email, context):
        ctx = {"email":email, "current_site":get_current_site(globals()["context"].request)}
        ctx.update(context)
        msg = self.render_mail(template_prefix, email, ctx)
        msg.send()

    def send_account_already_exists_mail(self, email):
        signup_url = build_absolute_uri(context.request, reverse("account_signup"))
        password_reset_url = build_absolute_uri(context.request, reverse("account_reset_password"))
        ctx = {
            "request": context.request,
            "signup_url": signup_url,
            "password_reset_url": password_reset_url,
        }
        self.send_mail("account/email/account_already_exists", email, ctx)

    def get_email_confirmation_url(self, request, emailconfirmation): # OBTENER URL DE EMAIL DE CONFIRMACION
        # URL Relativa: "/profile/"
        #pdb.set_trace()
        url = reverse("account_confirm_email", args=[emailconfirmation.key])
        #URL Absoluta: "https://www.example.com/profile/"
        ret = build_absolute_uri(request, url) # construir URL absoluta. incluyendo el esquema (http o https), el nombre de dominio y el puerto.
        return ret

    def send_confirmation_mail(self, request, emailconfirmation, signup): # ENVIAR EMAIL DE CONFIRMACION
        activate_url = self.get_email_confirmation_url(request, emailconfirmation)
        ctx = {
            "user": emailconfirmation.email_address.user,
            "activate_url": activate_url,
            "key": emailconfirmation.key,
        }
        if signup:
            email_template = "account/email/email_confirmation_signup"
        else:
            email_template = "account/email/email_confirmation"
        self.send_mail(email_template, emailconfirmation.email_address.email, ctx) # enviar email()

    def should_send_confirmation_mail(self, request, email_address, signup): # DEBE ENVIAR CONFIRMACION POR EMAIL
        from account.models import EmailConfirmation

        cooldown_period = timedelta(seconds=app_settings.EMAIL_CONFIRMATION_COOLDOWN) 
        if app_settings.EMAIL_CONFIRMATION_HMAC: # si habilitada
            send_email = ratelimit.consume(
                request,
                action="confirm_email",
                key=email_address.email.lower(),
                amount=1,
                duration=cooldown_period.total_seconds(),
            )
        else:
            send_email = not EmailConfirmation.objects.filter(sent__gt=timezone.now() - cooldown_period, email_address=email_address,).exists()
        return send_email # True-False

    def stash_verified_email(self, request, email): # ESCONDER EMAIL VERIFICADO
        request.session["account_verified_email"] = email # request.session = {'account_verified_email': email}

    def unstash_verified_email(self, request): # DESEMPAQUETAR EMAIL VERIFICADO
        ret = request.session.get("account_verified_email") # ret = request.session = {'account_verified_email':value}   ---> ret = value
        request.session["account_verified_email"] = None # request.session = {'account_verified_email': None}
        return ret

    def stash_user(self, request, user): # ESCONDER USUARIO
        request.session["account_user"] = user 

    def unstash_user(self, request): # DESESCONDER USUARIO
        return request.session.pop("account_user", None) # eliminar y obtener el valor de la key 'account_user', None si clave no existe en "request.session"

    def validate_unique_email(self, email): # VALIDACION EMAIL UNICO
        return email

def get_adapter(request=None):
    # import_atribute(...) -> importa dinamicamente un modulo o un atributo dentro de un modulo
    return import_attribute(app_settings.ADAPTER)(request) 