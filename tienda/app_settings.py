class AppSettings(object):
    def __init__(self, prefix):
        self.prefix = prefix

    def _setting(self, name, dflt):
        from Alpha.utils import get_setting
        return get_setting(self.prefix + name, dflt)
    
    @property
    def NAME_MAX_LENGTH(self):
        return self._setting('NAME_MAX_LENGTH', 30)
    
_app_settings = AppSettings("TIENDA_")

def __getattr__(name):
    return getattr(_app_settings, name)
