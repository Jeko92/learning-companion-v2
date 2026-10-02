from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.shortcuts import resolve_url
from django.views.generic import CreateView

from accounts.forms import SignUpForm


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"

    def get_success_url(self):
        return resolve_url(settings.LOGIN_REDIRECT_URL)

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        messages.success(self.request, f"Welcome, {self.object.get_username()}!")
        return response
