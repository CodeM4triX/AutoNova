from account.adapter import get_adapter
from account.utils import resume_login, stash_login, unstash_login
from Alpha.utils import import_callable

class LoginStage: # ETAPA DE INICIO DE SESION
    key = None #  atributo de clase llamado key y lo inicializa como None.
    def __init__(self, controller, request, login): 
        if not self.key: # self.key = None
            raise ValueError()
        self.controller = controller
        self.request = request
        self.login = login
        self.state = (self.login.state.setdefault("stages", {}).setdefault(self.key, {}).setdefault("data", {}))

    def handle(self): # MANEJAR
        return None, True

    def exit(self): # SALIDA
        self.controller.set_handled(self.key) # Llama a un método "set_handled" en el controlador y pasa "self.key" como argumento.
        return resume_login(self.request, self.login) # reanudar_inicio_sesion()

class LoginStageController: # CONTROLADOR DE ETAPA DE INICIO DE SESION
    def __init__(self, request, login):
        self.request = request
        self.login = login
        self.state = self.login.state.setdefault("stages", {}) # objeto.atributo.def()

    @classmethod
    def enter(cls, request, stage_key): # INGRESAR
        login = unstash_login(request, peek=True) # from allauth.account.utils import resume_login, stash_login, unstash_login      
        if not login:
            return None          
        ctrl = LoginStageController(request, login) # Crea una instancia de "LoginStageController" pasando la solicitud y el objeto de inicio de sesión
        if ctrl.state.get("current") != stage_key: # etapa actual almacenada en el estado del controlador != clave de la etapa a la que se desea ingresar
            return None      
        stages = ctrl.get_stages() # Obtiene todas las etapas disponibles del proceso de inicio de sesión utilizando el método get_stages() del controlador.
        for stage in stages:
            if stage.key == stage_key: # clave de la etapa actual == clave de la etapa a la que se dese ingresar
                return stage
        return None

    def set_current(self, stage_key): # ESTABLECER ACTUAL
        self.state["current"] = stage_key # self.estate = {'current':stage_key}

    def is_handled(self, stage_key): # ES MANEJADO
        return self.state.get(stage_key, {}).get("handled", False)

    def set_handled(self, stage_key): 
        stage_state = self.state.setdefault(stage_key, {})
        stage_state["handled"] = True # stage_state = {'handled': True}

    def get_stages(self): # OBTENER ETAPAS
        stages = [] # list
        adapter = get_adapter(self.request) # from allauth.account.adapter import get_adapter
        paths = adapter.get_login_stages() # llama al metodo get_login_stages() del adaptador para obtener las rutas (o nombres de clase) 
        for path in paths: #  Itera sobre todas las rutas de las etapas obtenidas.
            cls = import_callable(path) # importar la clase correspondiente a la ruta actual.
            stage = cls(self, self.request, self.login) 
            stages.append(stage) # Agrega la instancia de la etapa actual a la lista stages.
        return stages # Retorna la lista de instancias de etapas, que representa todas las etapas disponibles del proceso de inicio de sesión.

    def handle(self):
        stages = self.get_stages() # Obtiene todas las etapas disponibles del proceso de inicio de sesión del controlador
        for stage in stages: #  Itera sobre todas las etapas disponibles.
            if self.is_handled(stage.key): #  Verifica si la etapa actual ya ha sido manejada
                continue
            self.set_current(stage.key) #  Marca la etapa actual como la etapa actual en el estado del controlador utilizando el método set_current()
            response, cont = stage.handle()
            if response: #  Verifica si hay una respuesta de la etapa.
                if cont: # si se debe continuar con el proceso de login después de la etapa actual.
                    stash_login(self.request, self.login) # from allauth.account.utils import resume_login, stash_login, unstash_login
                else:
                    unstash_login(self.request) # Elimina cualquier objeto de inicio de sesión almacenado en la solicitud HTTP
                return response # Retorna la respuesta de la etapa actual.
            else:
                assert cont # afirmar cont=True ->  lo que significa que se debe continuar con el proceso de inicio de sesión.
        unstash_login(self.request) 
        
