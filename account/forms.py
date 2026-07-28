from importlib import import_module
from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import exceptions, validators
from django.urls import NoReverseMatch, reverse
from django.utils.safestring import mark_safe
from django.utils.translation import gettext, gettext_lazy as _, pgettext

from Alpha.utils import (build_absolute_uri, get_username_max_length, set_form_field_order)
from .authentication import record_authentication
from . import app_settings
from .adapter import get_adapter
from .app_settings import AuthenticationMethod
from .models import EmailAddress
from .utils import (assess_unique_email, get_user_model, setup_user_email, user_email, user_username, perform_login,
filter_users_by_email, filter_users_by_username, sync_user_email_addresses, user_pk_to_url_str, url_str_to_user_pk,
)

class PasswordField(forms.CharField):
    def __init__(self, *args, **kwargs):
        render_value = kwargs.pop("render_value", app_settings.PASSWORD_INPUT_RENDER_VALUE) # False
        # se configura el widget del campo de contraseña
        kwargs["widget"] = forms.PasswordInput(render_value= render_value, attrs={"placeholder": kwargs.get("label")})
        
        autocomplete = kwargs.pop("autocomplete", None)
        if autocomplete is not None:
            kwargs["widget"].attrs["autocomplete"] = autocomplete

        super().__init__(*args, **kwargs)

class _DummyCustomSignupForm(forms.Form):
    def signup(self, request, user):
        pass

def _base_signup_form_class():
    if not app_settings.SIGNUP_FORM_CLASS: # SIGNUP_FORM_CLASS -> si no esta definida en app_settings
        return _DummyCustomSignupForm  # se devuelve class _DummyCustomSignupForm
    try:
        fc_module, fc_classname = app_settings.SIGNUP_FORM_CLASS.rsplit(".", 1) # ["azul", "rojo, amarillo, naranja"]
    except ValueError:
        raise exceptions.ImproperlyConfigured("%s does not point to a form class" % app_settings.SIGNUP_FORM_CLASS)
    try:
        mod = import_module(fc_module) # importar modulo (fc_module)
    except ImportError as e:
        raise exceptions.ImproperlyConfigured("Error importing form class %s:" ' "%s"' % (fc_module, e))
    try:
        fc_class = getattr(mod, fc_classname) # obtener attr 'fc_classname' del modulo importado
    except AttributeError:
        raise exceptions.ImproperlyConfigured('Module "%s" does not define a' ' "%s" class' % (fc_module, fc_classname))
    if not hasattr(fc_class, "signup"):
        raise exceptions.ImproperlyConfigured("The custom signup form must offer"" a `def signup(self, request, user)` method",)
    return fc_class

class BaseSignupForm(_base_signup_form_class()):
    username = forms.CharField(
        label=_("Username"),
        min_length=app_settings.USERNAME_MIN_LENGTH,
        widget=forms.TextInput(
            attrs={"placeholder": _("Username"), "autocomplete": "username"}
        ),
    )
    email = forms.EmailField(
        widget=forms.TextInput(
            attrs={
                "type": "email",
                "placeholder": _("Email address"),
                "autocomplete": "email",
            }
        )
    )

    def __init__(self, *args, **kwargs):
        email_required = kwargs.pop("email_required", app_settings.EMAIL_REQUIRED) # kwargs.pop() -> eliminar y obtener el valor de una clave dada
        self.username_required = kwargs.pop("username_required", app_settings.USERNAME_REQUIRED)
        self.account_already_exists = False # se crea un atributo con valor False
        
        super(BaseSignupForm, self).__init__(*args, **kwargs) # __init__()
        
        username_field = self.fields["username"] # username_field = self.fields={'username': value} ---> se obtine el campo del formulario 'username'
        username_field.max_length = get_username_max_length() # objeto.atributo = value  ---> se le asigna una longitud maxima al campo 'username'
        
        username_field.validators.append(validators.MaxLengthValidator(username_field.max_length)) # objeto.modulo.append(modulo.metodo())
        username_field.widget.attrs["maxlength"] = str(username_field.max_length) # widget = forms.TextInput(attr={clave:valor}) 
        
        # email2 -> ignored when not present
        default_field_order = [
            "email",
            "email2",  
            "username",
            "password1",
            "password2", 
        ]
        if app_settings.SIGNUP_EMAIL_ENTER_TWICE: # si en app_settings esta habilitada   REGISTRAR EMAIL INGRESAR DOS VECES
            self.fields["email2"] = forms.EmailField(
                label=_("Email (again)"),
                widget=forms.TextInput(
                    attrs={
                        "type": "email",
                        "placeholder": _("Email address confirmation"),
                    }
                ),
            )
        if email_required: # si valor es diferente a None o (no es vacia)
            self.fields["email"].label = gettext("Email") # gettext() -> para traducir cadenas de texto. internacionalización (i18n) de Django
            self.fields["email"].required = True # campo email del formulario(self). el atributo required se define en True
        else:
            self.fields["email"].label = gettext("Email (optional)")
            self.fields["email"].required = False
            self.fields["email"].widget.is_required = False
            if self.username_required: # si valor es diferente a None (no es vacio) 
                # ignored email2 when not present
                # default_field_order -> variable para definir el orden predeterminado de los campos en el formulario
                default_field_order = [
                    "username",
                    "email",
                    "email2",
                    "password1",
                    "password2", 
                ]

        if not self.username_required: # si valor es None o (esta vacio)
            del self.fields["username"] # eliminar el campo username
        set_form_field_order(self, getattr(self, "field_order", None) or default_field_order) # establecer orden de los campos del formulario

    def clean_username(self): # LIMPIO USERNAME
        value = self.cleaned_data["username"]
        value = get_adapter().clean_username(value)
        return value

    def clean_email(self): # LIMPIO EMAIL
        value = self.cleaned_data["email"]
        value = get_adapter().clean_email(value)
        if value and app_settings.UNIQUE_EMAIL:
            value = self.validate_unique_email(value)
        return value

    def validate_unique_email(self, value): # VALIDACION DE EMAIL UNICO
        # pdb.set_trace() ------------------------------ >
        adapter = get_adapter()
        assessment = assess_unique_email(value) # evaluar email unico
        if assessment is True:
            pass
        elif assessment is False:
            raise forms.ValidationError(adapter.error_messages["email_taken"]) # objeto.atributo['email_taken']
        else:
            assert assessment is None # affirmar assesment is None
            self.account_already_exists = True # cuenta ya existe True
        return adapter.validate_unique_email(value) # objeto.metodo()

    def clean(self): # LIMPIO
        #pdb.set_trace()
        cleaned_data = super(BaseSignupForm, self).clean()
        if app_settings.SIGNUP_EMAIL_ENTER_TWICE: # registro email ingresar dos veces
            email = cleaned_data.get("email")
            email2 = cleaned_data.get("email2")
            if (email and email2) and email != email2: # si ambos email estan escritos y si emails son diferentes
                self.add_error("email2", _("You must(debe) type(escribir) the same email each(cada) time."))
        return cleaned_data

    def custom_signup(self, request, user): # REGISTRO PERSONALIZAR
        self.signup(request, user)  # se llama a la funcion registro()

    def try_save(self, request): # INTENTAR GUARDAR
        if self.account_already_exists: # self.account_already_exists = True
            # Don't create a new account, only send an email informing the user that (s)he already has one...
            email = self.cleaned_data["email"]
            adapter = get_adapter() # adapter -> objeto -> get_adapter()
            adapter.send_account_already_exists_mail(email) # enviar cuenta ya existe email
            user = None 
            resp = adapter.respond_email_verification_sent(request, None)
        else:
            user = self.save(request)  
            resp = None
        return user, resp

class SignupForm(BaseSignupForm):
    def __init__(self, *args, **kwargs):
        super(SignupForm, self).__init__(*args, **kwargs)
        self.fields["password1"] = PasswordField(
            label=_("Password"),
            autocomplete="new-password",
            help_text=password_validation.password_validators_help_text_html(),
        )
        if app_settings.SIGNUP_PASSWORD_ENTER_TWICE:
            self.fields["password2"] = PasswordField(
                label=_("Password (again)"),
                autocomplete="new-password"
            )
        if hasattr(self, "field_order"):
            set_form_field_order(self, self.field_order)

    def clean(self): # LIMPIO
        #pdb.set_trace()
        super(SignupForm, self).clean()
        User = get_user_model() # User -> obtiene el modelo de usuario 
        dummy_user = User()  # dummy_user -> creacion de una instancia de ese modelo de usuario 
        user_username(dummy_user, self.cleaned_data.get("username")) # user_username(user, *args, commit=False):
        user_email(dummy_user, self.cleaned_data.get("email"))
        password = self.cleaned_data.get("password1")
        if password:
            try:
                get_adapter().clean_password(password, user=dummy_user)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        if (app_settings.SIGNUP_PASSWORD_ENTER_TWICE and "password1" in self.cleaned_data and "password2" in self.cleaned_data):
            if self.cleaned_data["password1"] != self.cleaned_data["password2"]:
                self.add_error("password2",_("You must type the same password each time."),)
        return self.cleaned_data

    def save(self, request):
        email = self.cleaned_data.get("email")
        if self.account_already_exists:
            raise ValueError(email)
        adapter = get_adapter()
        user = adapter.new_user(request)
        adapter.save_user(request, user, self)
        self.custom_signup(request, user)
        setup_user_email(request, user, [EmailAddress(email=email)] if email else []) # setup_user_email(request, user, addresses):
        return user

class LoginForm(forms.Form):
    password = PasswordField(label=_("Password"), autocomplete="current-password")
    remember = forms.BooleanField(label=_("Remember Me"), required=False)
    user = None

    error_messages = {
        "account_inactive": _("This account is curently inactive"),
        "email_password_mismatch": _("The email address and/or password you specified are not correct."),
        "username_password_mismatch": _("The username and/or password you specified are not correct"),
    }
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super(LoginForm, self).__init__(*args, **kwargs)

        if app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.EMAIL:
            login_widget = forms.EmailInput(attrs={"placeholder":_("Email address"), "autocomplete": "email"})
            login_field = forms.EmailField(label=_("Email"), widget=login_widget)
        elif app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.USERNAME:
            login_widget = forms.TextInput(attrs={"placeholder": _("Username"), "autocomplete": "username"})
            login_field = forms.CharField(label=_("username"), widget=login_widget)
        else:
            assert (app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.USERNAME_EMAIL)
            login_widget = forms.TextInput(attrs={"placeholder": _("Username or Email"), "autocomplete": "email"})
            login_field = forms.CharField(label=pgettext("field label", "Login"), widget=login_widget)

        self.fields["login"] = login_field
        set_form_field_order(self, ["login", "password", "remember"])

        if app_settings.SESSION_REMEMBER is not None:
            del self.fields["remember"]
        try:
            reset_url = reverse("account_reset_password")
        except NoReverseMatch:
            pass
        else:
            forgot_txt = _("Forgot your password?")
            self.fields["password"].help_text = mark_safe(f"<a href='{reset_url}'>{forgot_txt}</a>")

    def user_credentials(self):
        credentials = {}
        login = self.cleaned_data["login"]

        if app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.EMAIL:
            credentials["email"] = login
        elif app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.USERNAME:
            credentials["username"] = login
        else:
            if self._is_login_email(login):
                credentials["email"] = login
            credentials["username"] = login
        credentials["password"] = self.cleaned_data["password"]
        return credentials

    def clean_login(self):
        login = self.cleaned_data["login"]
        return login.strip()

    def _is_login_email(self, login):
        try:
            validators.validate_email(login)
            ret = True
        except exceptions.ValidationError:
            ret = False
        return ret
    
    def clean(self):
        #pdb.set_trace()
        super(LoginForm, self).clean()
        if self._errors:
            #return
            raise forms.ValidationError("Mensaje de error:::::::::")
        credentials = self.user_credentials()
        user = get_adapter(self.request).authenticate(self.request, **credentials)
        if user:
            self.user = user
        else:
            auth_method = app_settings.AUTHENTICATION_METHOD
            if auth_method == app_settings.AuthenticationMethod.USERNAME_EMAIL:
                login = self.cleaned_data["login"]

                if self._is_login_email(login):
                    auth_method = app_settings.AuthenticationMethod.EMAIL
                else:
                    auth_method = app_settings.AuthenticationMethod.USERNAME
            raise forms.ValidationError(self.error_messages["%s_password_mismatch" % auth_method])
        return self.cleaned_data
    
    def login(self, request, redirect_url=None):
        credentials = self.user_credentials()
        extra_data = {field: credentials.get(field) for field in ["email", "username"] if field in credentials}

        record_authentication(request, method="password", **extra_data)

        ret = perform_login(
            request,
            self.user,
            email_verification=app_settings.EMAIL_VERIFICATION,
            redirect_url=redirect_url,
            email=credentials.get("email"),
        )
        remember = app_settings.SESSION_REMEMBER
        if remember is None:
            remember = self.cleaned_data["remember"]
        if remember:
            request.session.set_expiry(app_settings.SESSION_COOKIE_AGE)
        else:
            request.session.set_expiry(0)
        return ret

class EmailAwarePasswordResetTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp): # HACER VALOR PICADILLO
        ret = super(EmailAwarePasswordResetTokenGenerator, self)._make_hash_value(user, timestamp)
        sync_user_email_addresses(user)
        email = user_email(user)
        emails = set([email] if email else [])
        emails.update(EmailAddress.objects.filter(user=user).values_list("email", flat=True))
        ret += "|".join(sorted(emails))
        return ret

default_token_generator = app_settings.PASSWORD_RESET_TOKEN_GENERATOR()

class ResetPasswordForm(forms.Form):
    email = forms.EmailField(
        label="Email",
        required=True,
        widget = forms.TextInput(attrs={"type":"email", "placeholder":"Email Address", "autocomplete":"email"})
    )
    def clean_email(self):
        #pdb.set_trace()
        email = self.cleaned_data["email"]
        email = get_adapter().clean_email(email)
        self.users = filter_users_by_email(email, is_active=True, prefer_verified=True)
        print(f"-----> {self.users}") #prueba
        if not self.users and not app_settings.PREVENT_ENUMERATION:
            raise forms.ValidationError(get_adapter().error_messages["unknown_email"])
        return self.cleaned_data["email"]
    
    def save(self, request, **kwargs):
        email = self.cleaned_data["email"]
        if not self.users:
            if app_settings.EMAIL_UNKNOWN_ACCOUNTS:
                self._send_unknown_account_mail(request, email)
        else:
            self._send_password_reset_mail(request, email, self.users, **kwargs)
        return email

    def _send_unknown_account_mail(self, request, email):
        signup_url = build_absolute_uri(request, reverse("account_signup"))
        context = {"request": request, "signup_url": signup_url}
        get_adapter().send_mail("account/email/unknown_account", email, context)
    
    def _send_password_reset_mail(self, request, email, users, **kwargs):
        token_generator = kwargs.get("token_generator", default_token_generator)
        for user in users:
            temp_key = token_generator.make_token(user)
            uid = user_pk_to_url_str(user)
            path = reverse("account_reset_password_from_key", kwargs=dict(uidb36=uid, key=temp_key))
            url = build_absolute_uri(request, path)
            context = {"user":user, "password_reset_url":url, "uid":uid, "key":temp_key, "request":request}
            if app_settings.AUTHENTICATION_METHOD != AuthenticationMethod.EMAIL:
                context["username"] = user_username(user)
            get_adapter().send_mail("account/email/password_reset_key", email, context)

class PasswordVerificationMixin(object):
    def clean(self):
        cleaned_data = super(PasswordVerificationMixin, self).clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if (password1 and password2) and password1 != password2:
            self.add_error("password2", "You must type the same password each time")
        return cleaned_data

class SetPasswordField(PasswordField):
    def __init__(self, *args, **kwargs):
        kwargs["autocomplete"] = "new-password"
        super(SetPasswordField, self).__init__(*args, **kwargs)
        self.user = None
    
    def clean(self, value):
        value = super(SetPasswordField, self).clean(value)
        value = get_adapter().clean_password(value, user=self.user)
        return value

class ResetPasswordKeyForm(PasswordVerificationMixin, forms.Form):
    password1 = SetPasswordField(label="New password")
    password2 = PasswordField(label="New password (again)")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.temp_key = kwargs.pop("temp_key", None)
        super(ResetPasswordKeyForm, self).__init__(*args, **kwargs)
        self.fields["password1"].user = self.user

    def save(self):
        get_adapter().set_password(self.user, self.cleaned_data["password1"])

class UserTokenForm(forms.Form):
    uidb36 = forms.CharField()
    key = forms.CharField()
    reset_user = None
    token_generator = default_token_generator
    error_messages = {"token_invalid":"The password reset token was invalid"}

    def _get_user(self, uidb36):
        User = get_user_model()
        try:
            pk = url_str_to_user_pk(uidb36)
            return User.objects.get(pk=pk)
        except (ValueError, User.DoesNotExist):
            return None
    
    def clean(self):
        #pdb.set_trace()
        cleaned_data = super(UserTokenForm, self).clean() # return self._cleaned_data
        uidb36 = cleaned_data.get("uidb36", None)
        key = cleaned_data.get("key", None)
        if not key:
            raise forms.ValidationError(self.error_messages["token_invalid"])
        self.reset_user = self._get_user(uidb36)
        if self.reset_user is None or not self.token_generator.check_token(self.reset_user, key):
            raise forms.ValidationError(self.error_messages["token_invalid"])
        return cleaned_data
