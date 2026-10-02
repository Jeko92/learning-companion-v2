from django.views.generic import TemplateView

from accounts.forms import SignUpForm


class SignUpView(TemplateView):
    template_name = "accounts/signup.html"

    def get_context_data(self, **kwargs):
        return super().get_context_data(form=SignUpForm(), **kwargs)
