import base64
import importlib
import json
import random
import re
import string
import unicodedata
from collections import OrderedDict
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.core.files.base import ContentFile
from django.core.serializers.json import DjangoJSONEncoder
from django.core.validators import ValidationError, validate_email
from django.db.models import FileField
from django.db.models.fields import (BinaryField, DateField, DateTimeField, EmailField,TimeField,)
from django.utils import dateparse
from django.utils.encoding import force_bytes, force_str

def build_absolute_uri(request, location, protocol=None):
    from account import app_settings as account_settings
    #from django.contrib.sites.models import Site
    #pdb.set_trace()
    if request is None:
        """
        site = Site.objects.get_current()
        bits = urlsplit(location)
        if not (bits.scheme and bits.netloc):
            uri = "{proto}://{domain}{url}".format(
                proto=account_settings.DEFAULT_HTTP_PROTOCOL,
                domain=site.domain,
                url=location,
            )
        else:
            uri = location
        """
        pass
    else:
        uri = request.build_absolute_uri(location)
    if not protocol and account_settings.DEFAULT_HTTP_PROTOCOL == "https":
        protocol = account_settings.DEFAULT_HTTP_PROTOCOL
    if protocol:
        uri = protocol + ":" + uri.partition(".")[2]
    return uri

MAX_USERNAME_SUFFIX_LENGTH = 7
USERNAME_SUFFIX_CHARS = [string.digits] * 4 + [string.ascii_letters] * (MAX_USERNAME_SUFFIX_LENGTH - 4)

def _generate_unique_username_base(txts, regex=None):
    from account.adapter import get_adapter

    adapter = get_adapter()
    username = None
    regex = regex or r"[^\w\s@+.-]"
    for txt in txts:
        if not txt:
            continue
        username = unicodedata.normalize("NFKD", force_str(txt))
        username = username.encode("ascii", "ignore").decode("ascii")
        username = force_str(re.sub(regex, "", username).lower())
        username = username.split("@")[0]
        username = username.strip()
        username = re.sub(r"\s+", "_", username)
        try:
            username = adapter.clean_username(username, shallow=True)
            break
        except ValidationError:
            pass
    return username or "user"

def get_username_max_length():
    from account.app_settings import USER_MODEL_USERNAME_FIELD
    if USER_MODEL_USERNAME_FIELD is not None:
        User = get_user_model()
        max_length = User._meta.get_field(USER_MODEL_USERNAME_FIELD).max_length
    else:
        max_length = 0
    return max_length

def generate_username_candidate(basename, suffix_length):
    max_length = get_username_max_length()
    suffix = "".join(random.choice(USERNAME_SUFFIX_CHARS[i]) for i in range(suffix_length))
    return basename[0 : max_length - len(suffix)] + suffix

def generate_username_candidates(basename):
    from account.app_settings import USERNAME_MIN_LENGTH
    if len(basename) >= USERNAME_MIN_LENGTH:
        ret = [basename]
    else:
        ret = []
    min_suffix_length = max(1, USERNAME_MIN_LENGTH - len(basename))
    max_suffix_length = min(get_username_max_length(), MAX_USERNAME_SUFFIX_LENGTH)
    for suffix_length in range(min_suffix_length, max_suffix_length):
        ret.append(generate_username_candidate(basename, suffix_length))
    return ret


def generate_unique_username(txts, regex=None):
    from account.utils import filter_users_by_username
    from account.adapter import get_adapter
    from account.app_settings import USER_MODEL_USERNAME_FIELD

    adapter = get_adapter()
    basename = _generate_unique_username_base(txts, regex)
    candidates = generate_username_candidates(basename)
    existing_usernames = filter_users_by_username(*candidates).values_list(USER_MODEL_USERNAME_FIELD, flat=True)
    existing_usernames = set([n.lower() for n in existing_usernames])
    for candidate in candidates:
        if candidate.lower() not in existing_usernames:
            try:
                return adapter.clean_username(candidate, shallow=True)
            except ValidationError:
                pass
    raise NotImplementedError("Unable to find a unique username")

def get_form_class(forms, form_id, default_form):
    form_class = forms.get(form_id, default_form)
    if isinstance(form_class, str):
        form_class = import_attribute(form_class)
    return form_class

def get_request_param(request, param, default=None):
    if request is None:
        return default
    return request.POST.get(param) or request.GET.get(param, default)

def get_username_max_length():
    from account.app_settings import USER_MODEL_USERNAME_FIELD

    if USER_MODEL_USERNAME_FIELD is not None:
        User = get_user_model()
        max_length = User._meta.get_field(USER_MODEL_USERNAME_FIELD).max_length
    else: 
        max_length = 0
    return max_length

def set_form_field_order(form, field_order):
    if field_order is None:
        return
    fields = OrderedDict()
    for key in field_order:
        try:
            fields[key] = form.fields.pop(key)
        except KeyError: # ignore unknown fields
            pass
    fields.update(form.fields) # add remaining fields in original order
    form.fields = fields

def valid_email_or_none(email):
    ret = None
    try:
        if email:
            validate_email(email)
            if len(email) <= EmailField().max_length:
                ret = email
    except ValidationError:
        pass
    return ret

def import_attribute(path):
    assert isinstance(path, str)
    pkg, attr = path.rsplit(".", 1)
    ret = getattr(importlib.import_module(pkg), attr)
    return ret

def import_callable(path_or_callable):
    if not hasattr(path_or_callable, "__call__"):
        ret = import_attribute(path_or_callable)
    else:
        ret = path_or_callable
    return ret

def get_setting(name, dflt):
    getter = getattr(
        settings,
        "AUTHEN_SETTING_GETTER",
        lambda name, dflt: getattr(settings, name, dflt),
    )
    getter = import_callable(getter)
    return getter(name, dflt)
