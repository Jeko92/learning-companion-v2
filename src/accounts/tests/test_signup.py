from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import URLResolver, get_resolver, reverse

from accounts import urls as accounts_urls
from core.tests.html import PageParser

SIGNUP_PATH = "/accounts/signup/"
USERNAME = "alice"
# Passes all four configured password validators for USERNAME.
PASSWORD = "Tr4ck-Learning!"


def signup_data(username=USERNAME, password1=PASSWORD, password2=PASSWORD):
    return {"username": username, "password1": password1, "password2": password2}


class SignUpPageTests(TestCase):
    def test_signup_page_is_served_through_the_accounts_include(self):
        response = self.client.get(SIGNUP_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(reverse("accounts:signup"), SIGNUP_PATH)
        self.assertTemplateUsed(response, "accounts/signup.html")
        self.assertTemplateUsed(response, "base.html")
        # include() imports the module, so urlconf_name is the module itself.
        includes = [
            (str(pattern.pattern), pattern.namespace)
            for pattern in get_resolver().url_patterns
            if isinstance(pattern, URLResolver)
            and pattern.urlconf_name is accounts_urls
        ]
        self.assertEqual(includes, [("accounts/", "accounts")])

    def test_signup_page_renders_the_signup_form(self):
        response = self.client.get(SIGNUP_PATH)

        self.assertIn("form", response.context)
        form = response.context["form"]
        self.assertEqual(list(form.fields), ["username", "password1", "password2"])
        self.assertIs(form._meta.model, get_user_model())
        page = PageParser()
        page.feed(response.content.decode())
        forms = [attrs for tag, attrs in page.elements if tag == "form"]
        self.assertEqual(
            forms, [{"method": "post", "action": reverse("accounts:signup")}]
        )
        input_names = {
            attrs.get("name") for tag, attrs in page.elements if tag == "input"
        }
        self.assertLessEqual(
            {"csrfmiddlewaretoken", "username", "password1", "password2"},
            input_names,
        )


class SignUpSubmitTests(TestCase):
    def test_valid_signup_creates_one_user_with_a_hashed_password(self):
        self.client.post(SIGNUP_PATH, signup_data())

        users = get_user_model().objects.all()
        self.assertEqual(users.count(), 1)
        user = users.get()
        self.assertEqual(user.username, USERNAME)
        self.assertIs(user.check_password(PASSWORD), True)
        self.assertNotEqual(user.password, PASSWORD)

    def test_valid_signup_logs_the_user_in_and_redirects(self):
        response = self.client.post(SIGNUP_PATH, signup_data())

        user = get_user_model().objects.get(username=USERNAME)
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))
        self.assertEqual(settings.LOGIN_REDIRECT_URL, "/")
        self.assertRedirects(
            response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False
        )
