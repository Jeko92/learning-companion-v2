from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class SignUpForm(UserCreationForm):
    # UserCreationForm is bound to auth.User, which is swapped out in this
    # project, so point it at the custom user model.
    class Meta(UserCreationForm.Meta):
        model = get_user_model()
