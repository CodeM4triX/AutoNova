from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import PermissionDenied
from django.core.validators import validate_email
from django.forms import ValidationError
from django.http import (Http404, HttpResponse, HttpResponsePermanentRedirect, HttpResponseRedirect)
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic.base import TemplateResponseMixin, TemplateView, View
from django.views.generic.edit import FormView

from django.shortcuts import render
from Alpha.utils import get_form_class, get_request_param
from account import app_settings, signals
from account.forms import (SignupForm, LoginForm, ResetPasswordForm, ResetPasswordKeyForm, UserTokenForm)
from account.adapter import get_adapter
from account.models import (EmailAddress, EmailConfirmation, EmailConfirmationHMAC)
from account.utils import (
    passthrough_next_redirect_url,
    get_next_redirect_url,
    complete_signup,
    url_str_to_user_pk,
    perform_login,
)
from core import ratelimit
from core.internal.http import redirect
from core.exceptions import ImmediateHttpResponse

from tienda.models import Producto
from carro.views import ejecutar_limpiar_carro

# Create your views here.
def iniciar_session(request):
    return render(request, 'account/iniciar_session.html')
    
def _ajax_response(request, response, form=None, data=None):
    adapter = get_adapter()
    if adapter.is_ajax(request):
        if isinstance(response, HttpResponseRedirect) or isinstance(response, HttpResponsePermanentRedirect):
            redirect_to = response["location"]
        else:
            redirect_to = None
        response = adapter.ajax_response(request, response, form=form, data=data, redirect_to=redirect_to)
    return response
    
class AjaxCapableProcessFormViewMixin():
    def get(self, request, *args, **kwargs):
        response = super(AjaxCapableProcessFormViewMixin, self).get(request, *args, **kwargs)
        form = self.get_form()
        return _ajax_response(self.request, response, form=form, data=self._get_ajax_data_if())
    
    def post(self, request, *args, **kwargs):
        form_class = self.get_form_class()
        form = self.get_form(form_class)
        #pdb.set_trace()
        if form.is_valid():
            response = self.form_valid(form)
        else:
            response = self.form_invalid(form)
        return _ajax_response(self.request, response, form=form, data=self._get_ajax_data_if())

    def get_form(self, form_class=None):
        form = getattr(self, "_cached_form", None)
        if form is None:
            form = super(AjaxCapableProcessFormViewMixin, self).get_form(form_class)
            self._cached_form = form
        return form

    def _get_ajax_data_if(self):
        return (self.get_ajax_data() if get_adapter(self.request).is_ajax(self.request) else None)

    def get_ajax_data(self):
        return None

class CloseableSignupMixin():
    template_name_signup_closed = ("account/signup_closed." + app_settings.TEMPLATE_EXTENSION)
    def dispatch(self, request, *args, **kwargs):
        try:
            if not self.is_open():
                return self.closed()
        except ImmediateHttpResponse as e:
            return e.response
        return super(CloseableSignupMixin, self).dispatch(request, *args, **kwargs)
    
    def is_open(self):
        return get_adapter(self.request).is_open_for_signup(self.request)
    
    def closed(self):
        response_kwargs = {"request":self.request, "template":self.template_name_signup_closed,}
        return self.response_class(**response_kwargs)

class RedirectAuthenticatedUserMixin(object):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and app_settings.AUTHENTICATED_LOGIN_REDIRECTS: #
            redirect_to = self.get_authenticated_redirect_url() #
            response = HttpResponseRedirect(redirect_to)
            return response
        else:
            response = super(RedirectAuthenticatedUserMixin, self).dispatch(request, *args, **kwargs)
        return response
    """
    def get_authenticated_redirect_url(self):
        redirect_field_name = self.redirect_field_name
        return get_login_redirect_url(self.request, url=self.get_succes_url(), redirect_field_name=redirect_field_name)
    """
class LogoutFunctionalityMixin():
    def logout(self):
        adapter = get_adapter()
        adapter.add_message(self.request, messages.SUCCESS, "account/messages/logged_out.txt")
        adapter.logout(self.request)

class SignupView(RedirectAuthenticatedUserMixin, CloseableSignupMixin, AjaxCapableProcessFormViewMixin, FormView):
    template_name = "account/signup." + app_settings.TEMPLATE_EXTENSION
    form_class = SignupForm
    redirect_field_name = REDIRECT_FIELD_NAME
    success_url = None

    def dispatch(self, request, *args, **kwargs):
        return super(SignupView, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        ret = (get_next_redirect_url(self.request, self.redirect_field_name) or self.success_url)
        return ret

    def form_valid(self, form):
        self.user, resp = form.try_save(self.request)
        if resp:
            return resp
        try:
            return complete_signup(self.request, self.user, app_settings.EMAIL_VERIFICATION, self.get_success_url())
        except ImmediateHttpResponse as e:
            return e.response

    def get_context_data(self, **kwargs):
        ret = super(SignupView, self).get_context_data(**kwargs)
        form = ret["form"]
        email = self.request.session.get("account_verified_email")
        if email:
            email_keys = ["email"]
            if app_settings.SIGNUP_EMAIL_ENTER_TWICE:
                email_keys.append("email2")
            for email_key in email_keys:
                form.fields[email_key].initial = email
        # passthrough_next_redirect_url() -> get_next_redirect_url() -> (get_request_param(), get_adapter().is_safe_url())
        login_url = passthrough_next_redirect_url(self.request, reverse("account_login"), self.redirect_field_name)
        redirect_field_name = self.redirect_field_name   # 'next'
        site = get_current_site(self.request)   # <Site: http://127.0.0.1:8000>
        redirect_field_value = get_request_param(self.request, redirect_field_name)   # None
        ret.update(
            {
                "login_url": login_url,
                "redirect_field_name": redirect_field_name,
                "redirect_field_value": redirect_field_value,
                "site": site,
            }
        )
        return ret # {'form':<...>, 'view':<...>, 'login_url':'...', 'redirect_field_name':'next', 'site':<...>,}

    def get_form_class(self):
        return get_form_class(app_settings.FORMS, "signup", self.form_class) # <class 'allauth.account.forms.SignupForm'>

signup = SignupView.as_view()

class LoginView(RedirectAuthenticatedUserMixin, AjaxCapableProcessFormViewMixin, FormView):
    #pdb.set_trace()
    form_class = LoginForm
    template_name = "account/login." + app_settings.TEMPLATE_EXTENSION
    success_url = None
    redirect_field_name = REDIRECT_FIELD_NAME

    def dispatch(self, request, *args, **kwargs):
        return super(LoginView, self).dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super(LoginView, self).get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_form_class(self):
        return get_form_class(app_settings.FORMS, "login", self.form_class)

    def form_valid(self, form):
        success_url = self.get_success_url()
        try:
            return form.login(self.request, redirect_url=success_url)
        except ImmediateHttpResponse as e:
            return e.response

    def get_success_url(self):
        ret = (get_next_redirect_url(self.request, self.redirect_field_name) or self.success_url)
        return ret

    def get_context_data(self, **kwargs):
        ret = super(LoginView, self).get_context_data(**kwargs)
        signup_url = passthrough_next_redirect_url(self.request, reverse("account_signup"), self.redirect_field_name)
        redirect_field_value = get_request_param(self.request, self.redirect_field_name)
        site = get_current_site(self.request)
        
        ret.update(
            {
                "signup_url": signup_url,
                "site": site,
                "redirect_field_name": self.redirect_field_name,
                "redirect_field_value": redirect_field_value,
            }
        )
        return ret

login = LoginView.as_view()

class LogoutView(TemplateResponseMixin, LogoutFunctionalityMixin, View):
    template_name = "account/logout." + app_settings.TEMPLATE_EXTENSION
    redirect_field_name = REDIRECT_FIELD_NAME

    def get(self, *args, **kwargs):
        #pdb.set_trace()
        if app_settings.LOGOUT_ON_GET:
            return self.post(*args, **kwargs)
        if not self.request.user.is_authenticated:
            response = redirect(self.get_redirect_url())
            return _ajax_response(self.request, response)
        ctx = self.get_context_data()
        response = self.render_to_response(ctx)
        return _ajax_response(self.request, response)
    
    def post(self, request, *args, **kwargs):
        #pdb.set_trace()
        url = self.get_redirect_url()
        if self.request.user.is_authenticated:
            ejecutar_limpiar_carro(request)
            self.logout()
        response = redirect(url)
        return _ajax_response(self.request, response)

    def get_context_data(self, **kwargs):
        ctx = kwargs
        redirect_field_value = get_request_param(self.request, self.redirect_field_name)
        ctx.update(
            {
                "redirect_field_name": self.redirect_field_name,
                "redirect_field_value": redirect_field_value,
            }
        )
        return ctx
    
    def get_redirect_url(self):
        return get_next_redirect_url(
            self.request, self.redirect_field_name
            ) or get_adapter(self.request).get_logout_redirect_url(self.request)

logout = LogoutView.as_view()

class ConfirmEmailView(TemplateResponseMixin, LogoutFunctionalityMixin, View):
    template_name = "account/email_confirm." + app_settings.TEMPLATE_EXTENSION

    def get(self, *args, **kwargs):
        # args = <WSGIRequest: GET '/confirm-email/Mjk:1s4m6K:FphTw7yc0r3fT40llU1zlnZsrRFoC1GjyJU9trsVlSE/'>
        # kwargs = {'key': 'Mjk:1s4m6K:FphTw7yc0r3fT40llU1zlnZsrRFoC1GjyJU9trsVlSE'}
        try:
            self.object = self.get_object()
            self.logout_other_user(self.object)
            if app_settings.CONFIRM_EMAIL_ON_GET:
                return self.post(*args, **kwargs)
        except Http404:
            self.object = None
        ctx = self.get_context_data()
        return self.render_to_response(ctx)

    def post(self, *args, **kwargs):
        # args = <WSGIRequest: POST '/confirm-email/Mjk:1s4mAM:0U_v2Vwa0xNmIu_NJIM58yPIDA1BCIkKg-j6tmY7nYU/'>
        # kwargs = {'key': 'Mjk:1s4mAM:0U_v2Vwa0xNmIu_NJIM58yPIDA1BCIkKg-j6tmY7nYU'}
        self.object = confirmation = self.get_object()
        email_address = confirmation.confirm(self.request)
        if not email_address:
            get_adapter(self.request).add_message(
                self.request,
                message.ERROR,
                "account/messages/email_confirmation_failed.txt",
                {"email": confirmation.email_address.email},
            )
            return self.respond(False)
        self.logout_other_user(self.object)
        get_adapter(self.request).add_message(
            self.request,
            messages.SUCCESS,
            "account/messages/email_confirmed.txt",
            {"email": confirmation.email_address.email},
        )
        if app_settings.LOGIN_ON_EMAIL_CONFIRMATION:
            resp = self.login_on_confirm(confirmation)
            if resp is not None:
                return resp
        return self.respond(True)

    def respond(self, success):
        redirect_url = self.get_redirect_url()
        if not redirect_url:
            ctx = self.get_context_data()
            return self.render_to_response(ctx)
        return redirect(redirect_url)

    def logout_other_user(self, confirmation):
        if (self.request.user.is_authenticated and self.request.user.pk != confirmation.email_address.user_id):
            self.logout()

    def login_on_confirm(self, confirmation):
        user_pk = None
        user_pk_str = get_adapter(self.request).unstash_user(self.request)
        if user_pk_str:
            user_pk = url_str_to_user_pk(user_pk_str)
        user = confirmation.email_address.user
        if user_pk == user.pk and self.request.user.is_anonymous:
            return perform_login(
                self.request,
                user,
                app_settings.EmailVerificationMethod.NONE,
                redirect_url = self.get_redirect_url,
            )
        return None

    def get_object(self, queryset=None):
        key = self.kwargs["key"]
        #pdb.set_trace()
        emailconfirmation = EmailConfirmationHMAC.from_key(key)
        if not emailconfirmation:
            if queryset is None:
                queryset = self.get_queryset()
            try:
                emailconfirmation = queryset.get(key=key.lower())
            except EmailConfirmation.DoesNotExist:
                raise Http404()
        return emailconfirmation # <account.models.EmailConfirmationHMAC object at 0x0000019AD1B575B0>
    
    def get_queryset(self):
        qs = EmailConfirmation.objects.all_valid()
        qs = qs.select_related("email_address_user")
        return qs

    def get_context_data(self, **kwargs):
        ctx = kwargs
        site = get_current_site(self.request)
        ctx.update(
            {
                "site": site,
                "confirmation": self.object,
                "can_confirm": self.object and self.object.email_address.can_set_verified(),
            }
        )
        if self.object:
            ctx["email"] = self.object.email_address.email  
        return ctx

    def get_redirect_url(self):
        return get_adapter(self.request).get_email_confirmation_redirect_url(self.request)

confirm_email = ConfirmEmailView.as_view()

class EmailVerificationSentView(TemplateView):
    template_name = "account/verification_sent." + app_settings.TEMPLATE_EXTENSION
email_verification_sent = EmailVerificationSentView.as_view()

class PasswordResetView(AjaxCapableProcessFormViewMixin, FormView):
    template_name= "account/password_reset." + app_settings.TEMPLATE_EXTENSION
    form_class = ResetPasswordForm
    success_url = reverse_lazy("account_reset_password_done")
    redirect_field_name = REDIRECT_FIELD_NAME

    def get_form_class(self):
        return get_form_class(app_settings.FORMS, "reset_password", self.form_class)
    
    def form_valid(self, form):
        r429 = ratelimit.consume_or_429(self.request, action="reset_password_email", key=form.cleaned_data["email"].lower())
        if r429:
            return r429
        form.save(self.request)
        return super(PasswordResetView, self).form_valid(form)
    
    def get_context_data(self, **kwargs):
        ret = super(PasswordResetView, self).get_context_data(**kwargs)
        login_url = passthrough_next_redirect_url(self.request, reverse("account_login"), self.redirect_field_name)
        ret["password_reset_form"] = ret.get("form")
        ret.update({"login_url":login_url})
        return ret

password_reset = PasswordResetView.as_view()

class PasswordResetDoneView(TemplateView):
    template_name = "account/password_reset_done." + app_settings.TEMPLATE_EXTENSION
password_reset_done = PasswordResetDoneView.as_view()

INTERNAL_RESET_SESSION_KEY = "_password_reset_key"
class PasswordResetFromKeyView(AjaxCapableProcessFormViewMixin, LogoutFunctionalityMixin, FormView):
    template_name = "account/password_reset_from_key." + app_settings.TEMPLATE_EXTENSION
    form_class = ResetPasswordKeyForm
    success_url = reverse_lazy("account_reset_password_from_key_done")
    reset_url_key = "set-password"

    def dispatch(self, request, uidb36, key, **kwargs):
        self.request = request
        self.key = key
        user_token_form_class = get_form_class(app_settings.FORMS, "user_token", UserTokenForm)
        if self.key == self.reset_url_key:
            self.key = self.request.session.get(INTERNAL_RESET_SESSION_KEY, "")
            token_form = user_token_form_class(data={'uidb36':uidb36, 'key':self.key})
            if token_form.is_valid():
                self.reset_user = token_form.reset_user
                if (self.request.user.is_authenticated and self.request.user.pk != self.reset_user.pk):
                    self.logout()
                    self.request.session[INTERNAL_RESET_SESSION_KEY] = self.key
                return super(PasswordResetFromKeyView, self).dispatch(request, uidb36, self.key, **kwargs)
        else:
            token_form = user_token_form_class(data={'uidb36':uidb36, 'key':self.key})
            #pdb.set_trace()
            if token_form.is_valid():
                self.request.session[INTERNAL_RESET_SESSION_KEY] = self.key
                redirect_url = self.request.path.replace(self.key, self.reset_url_key)
                return redirect(redirect_url)
        self.reset_user = None
        response = self.render_to_response(self.get_context_data(token_fail=True))
        return _ajax_response(self.request, response, form=token_form)

    def get_form_class(self):
        return get_form_class(app_settings.FORMS, "reset_password_from_key", self.form_class)

    def get_context_data(self, **kwargs):
        ret = super(PasswordResetFromKeyView, self).get_context_data(**kwargs)
        ret["action_url"] = reverse(
            "account_reset_password_from_key",
            kwargs={'uidb36':self.kwargs["uidb36"], 'key':self.kwargs["key"]}
        )
        return ret
    
    def get_form_kwargs(self):
        kwargs = super(PasswordResetFromKeyView, self).get_form_kwargs()
        kwargs["user"] = self.reset_user
        kwargs["temp_key"] = self.key
        return kwargs

    def form_valid(self, form):
        form.save()
        adapter = get_adapter(self.request)
        if self.reset_user and app_settings.LOGIN_ATTEMPTS_LIMIT:
            for email in self.reset_user.emailaddress_set.all():
                adapter._delete_login_attempts_cached_email(self.request, email=email.email)
        adapter.add_message(self.request, messages.SUCCESS, "account/messages/pasword_changed.txt")
        signals.password_reset.send(sender=self.reset_user.__class__, request=self.request, user=self.reset_user)
        if app_settings.LOGIN_ON_PASSWORD_RESET:
            return perform_login(self.request, self.reset_user, email_verification=app_settings.EMAIL_VERIFICATION)
        return super(PasswordResetFromKeyView, self).form_valid(form)

password_reset_from_key = PasswordResetFromKeyView.as_view()

class PasswordResetFromKeyDoneView(TemplateView):
    template_name = "account/password_reset_from_key_done." + app_settings.TEMPLATE_EXTENSION
password_reset_from_key_done = PasswordResetFromKeyDoneView.as_view()

        

