from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from core.forms import StyledFormMixin


class LogInForm(StyledFormMixin, AuthenticationForm):
    """Django's log-in form, rendered like the project's other forms."""


class SignUpForm(StyledFormMixin, UserCreationForm):
    # UserCreationForm is bound to auth.User, which is swapped out in this
    # project, so point it at the custom user model.
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
