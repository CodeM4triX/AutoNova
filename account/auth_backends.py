from threading import local   # importa la clase local() del modulo "threading"

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from . import app_settings
from .app_settings import AuthenticationMethod
from .utils import filter_users_by_email, filter_users_by_username

_stash = local() # instancia de la clase local(). Esto se usa para almacenar datos que son específicos de la ejecución actual.
class AuthenticationBackend(ModelBackend):
    def authenticate(self, request, **credentials):
        #pdb.set_trace()
        ret = None # var ret -> será utilizada para almacenar el resultado de la autenticación.
        if app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.EMAIL: # Si el método de autenticación configurado es el email
            ret = self._authenticate_by_email(**credentials) # autenticar al usuario utilizando la función _authenticate_by_email con las credenciales            
        elif app_settings.AUTHENTICATION_METHOD == AuthenticationMethod.USERNAME_EMAIL: # Si el método de autenticación configurado es el username y email
            ret = self._authenticate_by_email(**credentials) # autenticar al usuario por email primero
            if not ret: # si autenticacion por email falla
                ret = self._authenticate_by_username(**credentials) # autenticar al usuario por el username
        else:
            ret = self._authenticate_by_username(**credentials) # autenticar al usuario por el username
        return ret # Devuelve el resultado de la autenticación. Si la autenticación es exitosa, ret contendrá el usuario autenticado. Si no, será None.

    def _authenticate_by_username(self, **credentials): # AUTENTICACION POR USERNAME
        username_field = app_settings.USER_MODEL_USERNAME_FIELD # obtienen el nombre del campo de nombre de usuario del modelo de usuario
        username = credentials.get("username") # credentials = {'username':value}
        password = credentials.get("password") # obtener el password proporcionados en las credenciales

        User = get_user_model() # obtiener la clase del modelo de usuario actualmente en uso en la aplicación.
        if not username_field or username is None or password is None:
            return None
        try:
            user = filter_users_by_username(username).get()
        except User.DoesNotExist: # usuario no existe
            get_user_model()().set_password(password) 
            return None
        else:
            if self._check_password(user, password): # verificar_contraseña
                return user

    def _authenticate_by_email(self, **credentials):
        email = credentials.get("email", credentials.get("username")) # obtener el valor de 'email', si no hay campo email. obtener el valor de 'username'
        if email:
            for user in filter_users_by_email(email, prefer_verified=True): # para todos los usuarios filtrados por email
                if self._check_password(user, credentials["password"]):
                    return user
        return None

    def _check_password(self, user, password):
        ret = user.check_password(password) # verifica si la contraseña proporcionada (password) coincide con la contraseña almacenada del usuario (user)
        if ret: # ret = True
            ret = self.user_can_authenticate(user) # verificar si el usuario puede autenticarse. 
            if not ret: # si not False = True
                self._stash_user(user)
        return ret

    @classmethod # significa que puede ser llamado en la clase misma en lugar de en una instancia de esa clase
    def _stash_user(cls, user): # USUARIO ESCONDIDO
        global _stash # stash variable global. Esto asegura que la variable _stash pueda ser modificada y accedida desde cualquier lugar en el módulo
        ret = getattr(_stash, "user", None) # obtener valor del atributo "user", de la variable global _stash
        _stash.user = user # Establece el atributo "user" en la variable global _stash con el valor del usuario pasado como argumento al método.
        return ret # devuelve valor previo del atributo "user" antes de que se cambiara en la línea anterior. Si no había ningún valor previo, devuelve None.

    @classmethod
    def unstash_authenticated_user(cls): # USUARIO AUTENTICADO
        return cls._stash_user(None) #  llama al método _stash_user con None como argumento. para desapilar o deshacer el ultimo usuario almacenado en _stash
