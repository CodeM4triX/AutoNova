import functools
from datetime import timedelta

from django.db import models
from django.db.models import Q
from django.utils import timezone

from . import app_settings

# EmailAddressManager -> hereda de models.Manager, lo que significa que esta clase actúa como un administrador de modelos para un modelo especifico
class EmailAddressManager(models.Manager):
    def can_add_email(self, user): # PUEDE AGREGAR EMAIL
        ret = True # Se inicializa una variable llamada ret con el valor True. Esta variable se usará para almacenar el resultado de la verificación.
        if app_settings.CHANGE_EMAIL:
            return True
        elif app_settings.MAX_EMAIL_ADDRESSES: # Si la primera condición no se cumple, esta parte se ejecutará.
            count = self.filter(user=user).count() # Cuenta la cantidad de direcciones de correo electrónico asociadas con el usuario dado
            ret = count < app_settings.MAX_EMAIL_ADDRESSES # ret = 6 < 9  => True
        return ret # ret, que indica si el usuario puede agregar una dirección de correo electrónico 

    def get_new(self, user): # OBTENER NUEVO
        assert app_settings.CHANGE_EMAIL
        return (self.model.objects.filter(user=user, verified=False).order_by("pk").last())

    def add_new_email(self, request, user, email): # AGREGAR NUEVO EMAIL
        assert app_settings.CHANGE_EMAIL
        instance = self.get_new(user) #  obtener email que el usuario está en proceso de cambiar
        if not instance: # Si no hay ninguna instancia en proceso de cambio de email
            instance = self.model.objects.create(user=user, email=email) # crea una nueva instancia de email del modelo con el usuario y email proporcionados
        else:
            instance.email = email
            instance.verified = False
            instance.primary = False
            instance.save()
        instance.send_confirmation(request) # Se envía una confirmación por email para verificar el email nuevo
        return instance # Se devuelve la instancia del email que se agregó o se actualizó.

    def add_email(self, request, user, email, confirm=False, signup=False): # AGREGAR EMAIL
        email_address, created = self.get_or_create(user=user, email__iexact=email, defaults={"email": email})
        if created and confirm: # created=True and confirm=True
            email_address.send_confirmation(request, signup=signup) 
        return email_address # Se devuelve la instancia del email, ya sea la existente recuperada o la recién creada.

    def get_verified(self, user):
        return self.filter(user=user, verified=True).order_by("-primary", "pk").first()

    def get_primary(self, user):
        try:
            return self.get(user=user, primary=True) # obtener objeto con estos criterios del modelo self("EmailAddress")
        except self.model.DoesNotExist:
            return None

    def get_primary_email(self, user): # OBTENER EMAIL PRINCIPAL
        from account.utils import user_email

        primary = self.get_primary(user) # obtener email principal asociada con el usuario dado (user)
        if primary:
            email = primary.email 
        else:
            email = user_email(user) # obtener email principal predeterminada del usuario.
        return email # Se devuelve email obtenida, ya sea email principal encontrada o email predeterminada del usuario

    def get_users_for(self, email):
        return [address.user for address in self.filter(verified=True, email__iexact=email)]

    def fill_cache_for_user(self, user, addresses): # RELLENAR CACHE PARA USUARIO
        user._emailaddress_cache = addresses # Asigna la lista de emails (addresses) a un atributo llamado "_emailaddress_cache" del objeto de usuario "user"

    def get_for_user(self, user, email):
        cache_key = "_emailaddress_cache" # Se define una clave de caché (cache_key) que se utilizará para acceder a la caché de emails del usuario.
        addresses = getattr(user, cache_key, None) # obtener el valor del atributo "cache_key", del objeto user
        if addresses is None:
            ret = self.get(user=user, email__iexact=email) # obtener email correspondiente al "user" y "email" proporcionados
            ret.user = user
            return ret # return la instancia del email obtenido
        else:
            for address in addresses:
                if address.email.lower() == email.lower(): # Si se encuentra un email que coincide  con el email proporcionado:
                    return address    # return email
            raise self.model.DoesNotExist() # Esto indica que email buscada no está en la caché 

    def is_verified(self, email):
        return self.filter(email__iexact=email, verified=True).exists() # return True si existe

    def lookup(self, emails): # BUSCAR
        q_list = [Q(email__iexact=e) for e in emails]    # q_list = [Q1, Q2, Q3]
        if not q_list: # Se verifica si la lista de consultas está vacía.   
            return self.none() # se devuelve un conjunto vacío utilizando self.none()
        q = functools.reduce(lambda a, b: a | b, q_list) # Esto crea una única consulta que busca emails que cumplan con cualquiera de las condiciones
        return self.filter(q)

class EmailConfirmationManager(models.Manager):
    def all_expired(self):
        return self.filter(self.expired_q())

    def all_valid(self):
        return self.exclude(self.expired_q()).filter(email_address__verified=False)

    def expired_q(self):
        sent_threshold = timezone.now() - timedelta(days=app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)
        return Q(sent__lt=sent_threshold) # se crea y devuelve una consulta "Q"

    def delete_expired_confirmations(self):
        self.all_expired().delete()
