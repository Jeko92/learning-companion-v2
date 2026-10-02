from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """The project's user model.

    It adds nothing to AbstractUser yet. It exists so the user model can change
    later without swapping AUTH_USER_MODEL mid-project. Refer to it through
    get_user_model() or settings.AUTH_USER_MODEL.
    """
