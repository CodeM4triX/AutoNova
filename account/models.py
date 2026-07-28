import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.db import models
from django.db.models import Index, Q
from django.db.models.constraints import UniqueConstraint
from django.db.models.functions import Upper
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from . import app_settings, signals
from .adapter import get_adapter
from .managers import EmailAddressManager, EmailConfirmationManager

# Create your models here.
class EmailAddress(models.Model):
    # ClaveForanea -> si objeto AUTH_USER_MODEL se elimina. tambien se eliminan todos los objetos EmailAddress relacionados
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    email = models.EmailField(max_length=app_settings.EMAIL_MAX_LENGTH)
    verified = models.BooleanField(default=False)
    primary = models.BooleanField(default=False)

    objects = EmailAddressManager()
    
    class Meta:
        # unico juntos
        verbose_name = "email address"
        verbose_name_plural = "email addresses"
        unique_together = [("user", "email")] # user no puede tener mismo email asociado mas de una vez
        if app_settings.UNIQUE_EMAIL:
            constraints = [
                UniqueConstraint(
                    fields = ["email"],
                    name = "unique_verified_email",
                    condition = Q(verified=True)
                )
            ]
        # indexes = [Index(Upper("email"), name="account_emailaddress_upper")]
    def __str__(self): # Devuelve la cadena representativa del objeto
        return self.email

    def can_set_verified(self): # PUEDE ESTABLECER VERIFICADO
        if self.verified: # si verified es True -> significa que email ya esta verificado
            return True
        conflict = False
        if app_settings.UNIQUE_EMAIL: # si UNIQUE_EMAIL esta activada (True), si es asi se realiza una consulta a BBDD
            conflict = (
                EmailAddress.objects.exclude(pk=self.pk).filter(verified=True, email__iexact=self.email).exists()
            )
        return not conflict # En lógica booleana, not False es True, y not True es False   ----------> retorn True

    def set_verified(self, commit=True): # ESTABLECER VERIFICADO
        if self.verified: # es una referencia al valor del campo verified en la instancia actual de la clase EmailAddress
            return True
        if self.can_set_verified(): # si email self.can_set_verified() -> return True   significa no hay conflictos y email puede ser verificada
            self.verified = True # self.verified= True -> se establece verificado en True
            if commit: # si commit = True
                self.save(update_fields=["verified"]) # se guarda la instancia en la BBDD, actulizando solo el campo 'verified'
        return self.verified # True

    def set_as_primary(self, conditional=False): # ESTABLECER COMO PRIMARIA
        from account.utils import user_email

        old_primary = EmailAddress.objects.get_primary(self.user) # obtine la direccion email primaria asociada al usuario especifico self.user
        if old_primary: 
            if conditional: # si condicion es True, se devuelve False, indicando que no se puede marcar la direccion actual como Primaria
                return False
            old_primary.primary = False  # se desmarca la direccion email primaria actual, y se guarda
            old_primary.save()
        self.primary = True # se marca la instancia actual como direccion email primaria, y se guarda
        self.save()
        user_email(self.user, self.email, commit=True)
        return True

    def send_confirmation(self, request=None, signup=False): # ENVIAR CONFIRMACION
        if app_settings.EMAIL_CONFIRMATION_HMAC: # si EMAIL_CONFIRMATION_HMAC esta activada
            confirmation = EmailConfirmationHMAC(self) # se crea una instancia de EmailConfirmationHMAC utilizando la direccion email ('self')
        else:
            confirmation = EmailConfirmation.create(self) # llamada al metodo create() de la clase. (un metodo de tipo 'classmethod' o 'staticmethod')
        confirmation.send(request, signup=signup)
        return confirmation # return la instancia de confirmación, ya sea de tipo EmailConfirmationHMAC o EmailConfirmation

    def remove(self): # ELIMINAR
        from account.utils import user_email
        self.delete() # se elimina la instancia actual de EmailAddress.  Esto eliminará la fila correspondiente de la base de datos.
        if user_email(self.user) == self.email: # si self.email eliminada era la primaria 
            alt = (
                EmailAddress.objects.filter(user=self.user)
                .order_by("-verified")
                .first()
            )
            alt_email = ""
            if alt: # si alt Tiene una direccion email
                alt_email = alt.email # se obtiene el valor email del objeto alt -> alt.email
            user_email(self.user, alt_email, commit=True)

class EmailConfirmationMixin:
    def confirm(self, request): # CONFIRMAR EMAIL
        email_address = self.email_address # email_address -> almacena el valor del atributo 'email_address', del objeto actual 'self'
        if not email_address.verified: # si atributo 'verified' del objeto 'email_address' es 'False'
            confirmed = get_adapter().confirm_email(request, email_address) # llama def confirm_email(), a travez de def adapter()
            if confirmed: # si confirmed fue exitosa
                signals.email_confirmed.send(
                    sender=self.__class__,
                    request=request,
                    email_address=email_address,
                )
                return email_address # return email confirmada

    def send(self, request=None, signup=False): # ENVIAR
        get_adapter().send_confirmation_mail(request, self, signup) # se llama a la funcion send_confirmation_mail()
        signals.email_confirmation_sent.send(
            sender=self.__class__,
            request=request,
            confirmation=self,
            signup=signup,
        )

class EmailConfirmation(EmailConfirmationMixin, models.Model):
    email_address = models.ForeignKey(EmailAddress, verbose_name=_("email address"), on_delete=models.CASCADE)
    created = models.DateTimeField(verbose_name=_("created"), default=timezone.now) # creacion de la instancia EmailConfirmation
    sent = models.DateTimeField(verbose_name=_("sent"), null=True) # fecha en el que se envio el email de confirmacion -> null=True si email aun no se envio
    key = models.CharField(verbose_name=_("key"), max_length=64, unique=True) # campo key para almacenar una clave única asociada a la confirmación de email

    #objects -> ATRIBUTO -> se le asigna una instancia de la clase EmailConfirmationManager(), administrador de consultas personalizado para EmailConfirmation
    objects = EmailConfirmationManager()
    class Meta:
        verbose_name = _("email confirmation") # nombre descriptivo para el modelo EmailConfirmation(), para cuando se muestre en la interfaz
        verbose_name_plural = _("email confirmations")

    def __str__(self): # método __str__ en Python se utiliza para proporcionar una representación de cadena legible para objetos de una class
        return "confirmation for %s" % self.email_address

    @classmethod # classmethod se llaman en la clase en lugar de en una instancia y toman la propia clase 'cls' como el primer parametro en lugar de self
    def create(cls, email_address): # CREAR
        key = get_adapter().generate_emailconfirmation_key(email_address.email) # genera una clave de confirmacion email
        return cls._default_manager.create(email_address=email_address, key=key) #Devuelve la nueva instancia de EmailConfirmation creada por el método create

    def key_expired(self): # CLAVE EXPIRADA
        expiration_date = self.sent + datetime.timedelta(days=app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS) # fecha de expiracion
        return expiration_date <= timezone.now() # si fecha de expiracion es <= a la fecha actual. entonces la funcion key_expired devuelve True

    key_expired.boolean = True
    def confirm(self, request): # CONFIRMAR
        if not self.key_expired(): # En lógica booleana, not False es True, y not True es False
            return super().confirm(request) # si clave de confirmacion no ha expirado, se llama al metodo confirm() de la clase base

    def send(self, request=None, signup=False): # ENVIAR
        super().send(request=request, signup=signup)
        self.sent = timezone.now() # Establece la propiedad sent de la instancia actual con la fecha y hora actuales utilizando timezone.now()
        self.save() # Guarda la instancia actual en la BBDD. Necesario para persistir los cambios realizados, en este caso, actualización de la propiedad sent

class EmailConfirmationHMAC(EmailConfirmationMixin, object):
    def __init__(self, email_address): # metodo constructor se llama automaticamente cuando se crea una nueva instancia de la clase
        self.email_address = email_address

    @property # decorador utilizado para convertir un metodo en una propiedad, significa que este metodo puede ser llamado como si fuera un atributo
    def key(self):
        return signing.dumps(obj=self.email_address.pk, salt=app_settings.SALT)

    @classmethod # este tipo de metodo se llama en la clase, y toma la propia clase 'cls' como primer parametro
    def from_key(cls, key): 
        try:
            max_age = 60 * 60 * 24 * app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS # max_age -> contiene el tiempo máximo de validez de la firma en segundos
            pk = signing.loads(key, max_age=max_age, salt=app_settings.SALT) # key -> Es la firma que se desea cargar. generado con la función signing.dumps()
            ret = EmailConfirmationHMAC(EmailAddress.objects.get(pk=pk, verified=False))
        except (signing.SignatureExpired, signing.BadSignature,EmailAddress.DoesNotExist,):
            ret = None
        return ret

class Login:
    def __init__(self, user, email_verification, redirect_url=None, signal_kwargs=None, signup=False, email=None, state=None,):
        self.user = user # El usuario asociado a la instancia self
        self.email_verification = email_verification #  verificación de correo electrónico asociada al proceso de inicio de sesión.
        self.redirect_url = redirect_url # URL opcional a la cual redirigir después del inicio de sesión.
        self.signal_kwargs = signal_kwargs # Argumentos opcionales que pueden ser utilizados en las señales.
        self.signup = signup # indicador que indica si el usuario está registrándose o iniciando sesión.
        self.email = email # email asociada al proceso de inicio de sesión.
        self.state = {} if state is None else state # si state es None: self.state={} else: self.state = state

    def serialize(self):
        from account.utils import user_pk_to_url_str

        signal_kwargs = self.signal_kwargs # Copia la referencia al diccionario 'signal_kwargs' desde el atributo 'self.signal_kwargs'
        if signal_kwargs is not None: # si signal_kwargs no es None:
            sociallogin = signal_kwargs.get("sociallogin") # obtener el valor asociado con la clave "sociallogin" del diccionario 'signal_kwargs'
            if sociallogin is not None: # si sociallogin no es None:
                signal_kwargs = signal_kwargs.copy() # copia signal_kwargs={}. Esto se hace para evitar modificar directamente el diccionario original.
                signal_kwargs["sociallogin"] = sociallogin.serialize() # Llama al método serialize() en el objeto sociallogin.         
        data = {
            "user_pk": user_pk_to_url_str(self.user),
            "email_verification": self.email_verification,
            "signup": self.signup,
            "redirect_url": self.redirect_url,
            "email": self.email,
            "signal_kwargs": signal_kwargs,
            "state": self.state,
        }
        return data

    @classmethod
    def deserialize(cls, data):
        from account.utils import url_str_to_user_pk
        #from socialaccount.models import SocialLogin

        user = ( get_user_model().objects.filter(pk=url_str_to_user_pk(data["user_pk"])).first() )
        if user is None: 
            raise ValueError() # levanta una excepcion de tipo ValueError()
        try:
            signal_kwargs = data["signal_kwargs"] # del diccionario data={} obtener el valor de la clave ['signal_kwargs']
            if signal_kwargs is not None: # si valor no es None
                sociallogin = signal_kwargs.get("sociallogin") # del diccionario signal_kwargs={}, obtener el valor asociado con la clave ["sociallogin"]
                if sociallogin is not None: # valor no es None
                    signal_kwargs = signal_kwargs.copy() # copiar el diccionario signal_kwargs={} a 'signal_kwargs'
                    signal_kwargs["sociallogin"] = SocialLogin.deserialize(sociallogin) # signal_kwargs['sociallogin] = SocialLogin.deserialize() return ret
            return Login(
                user=user,
                email_verification=data["email_verification"],
                redirect_url=data["redirect_url"],
                signup=data["signup"],
                signal_kwargs=signal_kwargs,
                state=data["state"],
            )
        except KeyError: # Captura una excepción de tipo KeyError. si alguna de las claves necesarias no está presente en el diccionario data
            raise ValueError() #  En este caso, levanta una excepción de tipo ValueError.
