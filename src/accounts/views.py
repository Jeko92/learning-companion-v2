from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, resolve_url
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import CreateView

from accounts.forms import SignUpForm


@method_decorator(sensitive_post_parameters("password1", "password2"), name="dispatch")
class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"

    def dispatch(self, request, *args, **kwargs):
        # Like LoginView.redirect_authenticated_user: signed-in users don't sign up.
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return resolve_url(settings.LOGIN_REDIRECT_URL)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, f"Welcome, {self.object.get_username()}!")
        return response


class LogInView(auth_views.LoginView):
    template_name = "accounts/login.html"
    # Signed-in users go to LOGIN_REDIRECT_URL, as on sign-up.
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, f"Welcome back, {form.get_user().get_username()}!"
        )
        return response
