from django.core.exceptions import ImproperlyConfigured

class AppSettings(object):
    class AuthenticationMethod:
        # ACCEDER A LOS VALORES -> NOTACION DEL PUNTO  --->   AppSettings.AuthenticationMethod.USERNAME
        USERNAME = 'username'
        EMAIL = 'email'
        USERNAME_EMAIL = 'username_email'

    class EmailVerificationMethod:
        MANDATORY = 'mandatory'
        OPTIONAL = 'optional'
        NONE = 'none'
    
    def __init__(self, prefix):
        #pdb.set_trace()
        self.prefix = prefix
        assert (not self.AUTHENTICATION_METHOD == self.AuthenticationMethod.EMAIL) or self.EMAIL_REQUIRED
        assert (self.AUTHENTICATION_METHOD == self.AuthenticationMethod.USERNAME) or self.UNIQUE_EMAIL
        assert (self.EMAIL_VERIFICATION != self.EmailVerificationMethod.MANDATORY) or self.EMAIL_REQUIRED
        if not self.USER_MODEL_USERNAME_FIELD:
            assert not self.USERNAME_REQUIRED
            assert  self.AUTHENTICATION_METHOD not in (self.AuthenticationMethod.USERNAME, self.AuthenticationMethod.USERNAME_EMAIL)
        if self.MAX_EMAIL_ADDRESSES is not None:
            assert self.MAX_EMAIL_ADDRESSES > 0
        if self.CHANGE_EMAIL:
            if self.MAX_EMAIL_ADDRESSES is not None and self.MAX_EMAIL_ADRESSES != 2:
                raise ImproperlyConfigured("invalid combination of CHANGE_EMAIL and MAX_EMAIL_ADDRESSES")

    def _setting(self, name, dflt):
        from Alpha.utils import get_setting
        return get_setting(self.prefix + name, dflt)

    @property
    def ADAPTER(self):
        return self._setting("ADAPTER", "account.adapter.DefaultAccountAdapter")

    @property
    def AUTHENTICATED_LOGIN_REDIRECTS(self):
        return self._setting('AUTHENTICATED_LOGIN_REDIRECTS', True)

    @property
    def AUTHENTICATION_METHOD(self):
        ret = self._setting("AUTHENTICATION_METHOD", self.AuthenticationMethod.USERNAME)
        return ret

    @property
    def CHANGE_EMAIL(self):
        return self._setting("CHANGE_EMAIL", False)

    @property
    def CONFIRM_EMAIL_ON_GET(self):
        return self._setting("CONFIRM_EMAIL_ON_GET", False)

    @property 
    def DEFAULT_HTTP_PROTOCOL(self):
        return self._setting("DEFAULT_HTTP_PROTOCOL", "http").lower()

    @property
    def EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL(self): # URL DE REDIRECCIONAMIENTO DESPUES DE CONFIRMACION EMAIL ANONIMO
        from django.conf import settings
        return self._setting("EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL", settings.LOGIN_URL)

    @property
    def EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL(self): # URL DE REDIRECCIONAMIENTO DESPUES DE CONFIRMACION EMAIL AUTENTICADO
        return self._setting("EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL", None)

    @property
    def EMAIL_CONFIRMATION_HMAC(self):
        return self._setting("EMAIL_CONFIRMATION_HMAC", True)

    @property
    def EMAIL_CONFIRMATION_COOLDOWN(self): # TIEMPO DE ESPERA DE EMAIL CONFIRMATION
        return self._setting("EMAIL_CONFIRMATION_COOLDOWN", 3 * 60)

    @property
    def EMAIL_CONFIRMATION_EXPIRE_DAYS(self): # DIAS DE EXPIRACION DE EMAIL DE CONFIRMACION
        from django.conf import settings
        return self._setting("EMAIL_CONFIRMATION_EXPIRE_DAYS", getattr(settings, "EMAIL_CONFIRMATION_DAYS", 3))

    @property
    def EMAIL_MAX_LENGTH(self):
        return self._setting("EMAIL_MAX_LENGTH", 12)

    @property
    def EMAIL_REQUIRED(self):
        return self._setting("EMAIL_REQUIRED", False)

    @property
    def EMAIL_SUBJECT_PREFIX(self):
        return self._setting("EMAIL_SUBJECT_PREFIX", None)

    @property
    def EMAIL_VERIFICATION(self):
        ret = self._setting("EMAIL_VERIFICATION", self.EmailVerificationMethod.OPTIONAL)
        if ret is True:
            ret = self.EmailVerificationMethod.MANDATORY
        elif ret is False:
            ret = self.EmailVerificationMethod.OPTIONAL
        return ret

    @property
    def EMAIL_UNKNOWN_ACCOUNTS(self):
        return self._setting("EMAIL_UNKNOWN_ACCOUNTS", True)

    @property
    def FORMS(self):
        return self._setting("FORMS", {})

    @property
    def LOGIN_ATTEMPTS_LIMIT(self):
        return self._setting("LOGIN_ATTEMPTS_LIMIT", 5)

    @property
    def LOGIN_ATTEMPTS_TIMEOUT(self):
        return self._setting("LOGIN_ATTEMPTS_TIMEOUT", 60 * 5)

    @property
    def LOGIN_ON_EMAIL_CONFIRMATION(self):
        return self._setting("LOGIN_ON_EMAIL_CONFIRMATION", False)

    @property
    def LOGIN_ON_PASSWORD_RESET(self):
        return self._setting("LOGIN_ON_PASSWORD_RESET", False)

    @property
    def LOGOUT_ON_GET(self):
        return self._setting("LOGOUT_ON_GET", False)

    @property
    def LOGOUT_ON_PASSWORD_CHANGE(self):
        return self._setting("LOGOUT_ON_PASSWORD_CHANGE", False)

    @property
    def LOGOUT_REDIRECT_URL(self):
        from django.conf import settings
        return self._setting("LOGOUT_REDIRECT_URL", settings.LOGOUT_REDIRECT_URL or "/")

    @property
    def MAX_EMAIL_ADDRESSES(self):
        return self._setting("MAX_EMAIL_ADDRESSES", None)

    @property
    def PASSWORD_INPUT_RENDER_VALUE(self):
        return self._setting("PASSWORD_INPUT_RENDER_VALUE", False)

    @property
    def PASSWORD_MIN_LENGTH(self):
        from django.conf import settings
        ret = None
        if not settings.AUTH_PASSWORD_VALIDATORS:
            ret = self._setting("PASSWORD_MIN_LENGTH", 6)
        return ret

    @property
    def PASSWORD_RESET_TOKEN_GENERATOR(self):
        from account.forms import EmailAwarePasswordResetTokenGenerator
        from Alpha.utils import import_attribute
        
        token_generator_path = self._setting("PASSWORD_RESET_TOKEN_GENERATOR", None)
        if token_generator_path is not None:
            token_generator = import_attribute(token_generator_path) #importar generador de tokens según la configuración especificada en token_generator_path
        else:
            token_generator = EmailAwarePasswordResetTokenGenerator
        return token_generator

    @property
    def PRESERVE_USERNAME_CASING(self):
        return self._setting("PRESERVE_USERNAME_CASING", True)

    @property
    def PREVENT_ENUMERATION(self): # PREVENIR LA ENUMERACION
        return self._setting("PREVENT_ENUMERATION", True)

    @property
    def RATE_LIMITS(self):
        dflt = {
            # Change password view (for users already logged in)
            "change_password": "5/m", # 5/m   -> 5 veces por minuto  -> intentar cambiar password hasta 5 veces por minuto, antes de alcanzar limite de taza
            # Email management(gestion) (e.g. add, remove, change primary)
            "manage_email": "10/m",
            # Request a password reset, global rate limit per IP
            "reset_password": "20/m",
            # Rate limit measured(medida) per individual email address
            "reset_password_email": "5/m",
            # Reauthentication for users already logged in) 
            "reauthenticate": "10/m",
            # Password reset (the view the password reset email links to).
            "reset_password_from_key": "20/m",
            # Signups.
            "signup": "20/m",
        }
        return self._setting("RATE_LIMITS", dflt)
    
    @property
    def SALT(self):
        return self._setting("SALT", "account")

    @property
    def SESSION_COOKIE_AGE(self):
        from django.conf import settings
        return self._setting("SESSION_COOKIE_AGE", settings.SESSION_COOKIE_AGE)

    @property
    def SESSION_REMEMBER(self):
        return self._setting("SESSION_REMEMBER", None)

    @property
    def SIGNUP_EMAIL_ENTER_TWICE(self):
        return self._setting("SIGNUP_EMAIL_ENTER_TWICE", False)

    @property
    def SIGNUP_FORM_CLASS(self):
        return self._setting("SIGNUP_FORM_CLASS", None)

    @property
    def SIGNUP_PASSWORD_ENTER_TWICE(self):
        return self._setting("SIGNUP_PASSWORD_ENTER_TWICE", True)

    @property
    def SIGNUP_REDIRECT_URL(self): # URL DE REDIRECCIONAMIENTO DESPUES DE REGISTRO
        from django.conf import settings
        return self._setting("SIGNUP_REDIRECT_URL", settings.LOGIN_REDIRECT_URL)

    @property
    def UNIQUE_EMAIL(self):
        return self._setting("UNIQUE_EMAIL", True)

    @property
    def USERNAME_BLACKLIST(self):
        return self._setting("USERNAME_BLACKLIST", [])

    @property
    def USERNAME_MIN_LENGTH(self):
        return self._setting("USERNAME_MIN_LENGTH", 1)

    @property
    def USERNAME_REQUIRED(self):
        return self._setting("USERNAME_REQUIRED", True)

    @property
    def USERNAME_VALIDATORS(self):
        from django.contrib.auth import get_user_model
        from django.core.exceptions import ImproperlyConfigured
        from Alpha.utils import import_attribute

        path = self._setting("USERNAME_VALIDATORS", None)
        if path: # if path != None 
            ret = import_attribute(path) #  Importa los validadores de nombres de usuario según la configuración especificada en path.
            if not isinstance(ret, list):
                raise ImproperlyConfigured("ACCOUNT_USERNAME_VALIDATORS is expected to be a list") # if los validadores no son una lista, se genera excepcion
        else: # path = None
            if self.USER_MODEL_USERNAME_FIELD is not None: 
                ret = (get_user_model()._meta.get_field(self.USER_MODEL_USERNAME_FIELD).validators)
            else:
                ret = []
        return ret

    @property
    def USER_MODEL_EMAIL_FIELD(self):
        return self._setting("USER_MODEL_EMAIL_FIELD", "email")

    @property
    def USER_MODEL_USERNAME_FIELD(self):
        return self._setting("USER_MODEL_USERNAME_FIELD", "username")

    @property
    def TEMPLATE_EXTENSION(self):
        return self._setting("TEMPLATE_EXTENSION", 'html')

_app_settings = AppSettings("ACCOUNT_")

# __getattr__ -> se llama automaticamente cuando se intenta acceder a un atributo que no existe en el objeto 
# en el que se llama
def __getattr__(name):
    return getattr(_app_settings, name)