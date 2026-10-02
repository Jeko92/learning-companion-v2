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

    def test_home_welcomes_the_new_user_after_signup(self):
        response = self.client.post(SIGNUP_PATH, signup_data(), follow=True)

        self.assertEqual(response.request["PATH_INFO"], "/")
        self.assertContains(response, f"Welcome, {USERNAME}!")


class SignUpInvalidTests(TestCase):
    # (case, submitted data, field with the error, error message). Only the two
    # duplicate cases collide with the existing user, so each case triggers
    # exactly the one error it is named after.
    CASES = (
        (
            "mismatched passwords",
            signup_data("bob", PASSWORD, "Different-Pass9!"),
            "password2",
            "The two password fields didn’t match.",
        ),
        (
            "existing username",
            signup_data(USERNAME),
            "username",
            "A user with that username already exists.",
        ),
        (
            "username differing only in case",
            signup_data("Alice"),
            "username",
            "A user with that username already exists.",
        ),
        (
            "common password",
            signup_data("bob", "password123", "password123"),
            "password2",
            "This password is too common.",
        ),
        (
            "short password",
            signup_data("bob", "Xq7#vB", "Xq7#vB"),
            "password2",
            "This password is too short. It must contain at least 8 characters.",
        ),
    )

    def setUp(self):
        get_user_model().objects.create_user(USERNAME, password=PASSWORD)

    def test_invalid_signup_rerenders_the_form_with_the_field_error(self):
        for case, data, field, message in self.CASES:
            with self.subTest(case=case):
                response = self.client.post(SIGNUP_PATH, data)

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "accounts/signup.html")
                form = response.context["form"]
                self.assertFormError(form, field, message)
                self.assertEqual(list(form.errors), [field])
                self.assertEqual(get_user_model().objects.count(), 1)
                self.assertNotIn("_auth_user_id", self.client.session)
                for password in {data["password1"], data["password2"]}:
                    self.assertNotContains(response, password)


class SignUpLoggedInTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.client.force_login(user)

    def test_logged_in_get_redirects_without_the_form(self):
        response = self.client.get(SIGNUP_PATH)

        self.assertRedirects(
            response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False
        )
        self.assertTemplateNotUsed(response, "accounts/signup.html")

    def test_logged_in_post_redirects_without_creating_a_user(self):
        response = self.client.post(SIGNUP_PATH, signup_data("bob"))

        self.assertRedirects(
            response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False
        )
        self.assertEqual(get_user_model().objects.count(), 1)
