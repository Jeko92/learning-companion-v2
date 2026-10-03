from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import NoReverseMatch, reverse

from core.tests.html import PageParser

LOGIN_PATH = "/accounts/login/"
USERNAME = "alice"
PASSWORD = "Tr4ck-Learning!"
# Where log-in lands without a usable next (dashboard-status AC9, AC10).
DASHBOARD = "/dashboard/"


def get_page(client, path):
    page = PageParser()
    page.feed(client.get(path).content.decode())
    return page


class LoginPageTests(TestCase):
    def test_login_page_is_served_at_the_login_url(self):
        response = self.client.get(LOGIN_PATH)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(reverse("accounts:login"), LOGIN_PATH)
        self.assertEqual(resolve_url(settings.LOGIN_URL), LOGIN_PATH)
        self.assertTemplateUsed(response, "accounts/login.html")
        self.assertTemplateUsed(response, "base.html")

    def test_login_page_renders_the_login_form(self):
        page = get_page(self.client, LOGIN_PATH)

        ((attrs, inputs),) = page.forms("main")
        # Only method and action, so styling attributes can't break the test.
        self.assertEqual(attrs.get("method"), "post")
        self.assertEqual(attrs.get("action"), reverse("accounts:login"))
        input_names = {attrs.get("name") for attrs in inputs}
        self.assertLessEqual(
            {"csrfmiddlewaretoken", "username", "password"}, input_names
        )

    def test_no_password_reset_or_change_routes_exist(self):
        # Only login and logout are wired, not django.contrib.auth.urls.
        for name in (
            "password_reset",
            "password_change",
            "accounts:password_reset",
            "accounts:password_change",
        ):
            with self.subTest(name=name), self.assertRaises(NoReverseMatch):
                reverse(name)


class LoginSubmitTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)

    def log_in(self, **extra):
        data = {"username": USERNAME, "password": PASSWORD, **extra}
        return self.client.post(LOGIN_PATH, data)

    def test_valid_login_logs_the_user_in_and_redirects(self):
        response = self.log_in()

        self.assertEqual(self.client.session.get("_auth_user_id"), str(self.user.pk))
        self.assertRedirects(response, DASHBOARD, fetch_redirect_response=False)

    def test_the_dashboard_welcomes_the_user_back(self):
        response = self.client.post(
            LOGIN_PATH, {"username": USERNAME, "password": PASSWORD}, follow=True
        )

        self.assertEqual(response.request["PATH_INFO"], DASHBOARD)
        self.assertContains(response, f"Welcome back, {USERNAME}!")


SAFE_NEXT = "/some/page/?a=1"
# Open-redirect payloads, including tricks that bypass naive checks.
UNSAFE_NEXTS = (
    "https://evil.example/",
    "//evil.example/",
    "/\\evil.example/",
    "\\\\evil.example",
    "javascript:alert(1)",
    "https://testserver.evil.example/",
)


class LoginNextTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(USERNAME, password=PASSWORD)

    def test_safe_next_is_carried_in_the_form_and_followed(self):
        response = self.client.get(LOGIN_PATH, {"next": SAFE_NEXT})
        page = PageParser()
        page.feed(response.content.decode())
        ((_, inputs),) = page.forms("main")
        next_values = [a.get("value") for a in inputs if a.get("name") == "next"]
        self.assertEqual(next_values, [SAFE_NEXT])

        response = self.client.post(
            LOGIN_PATH, {"username": USERNAME, "password": PASSWORD, "next": SAFE_NEXT}
        )

        self.assertRedirects(response, SAFE_NEXT, fetch_redirect_response=False)

    def test_unsafe_next_is_never_followed(self):
        # "query" pins that LoginView also validates a GET next; the browser
        # flow (the form posts only its hidden field) is covered below.
        credentials = {"username": USERNAME, "password": PASSWORD}
        for payload in UNSAFE_NEXTS:
            for via in ("post", "query"):
                with self.subTest(payload=payload, via=via):
                    self.client.logout()
                    if via == "post":
                        response = self.client.post(
                            LOGIN_PATH, {**credentials, "next": payload}
                        )
                    else:
                        url = f"{LOGIN_PATH}?{urlencode({'next': payload})}"
                        response = self.client.post(url, credentials)

                    self.assertIn("_auth_user_id", self.client.session)
                    self.assertRedirects(
                        response,
                        DASHBOARD,
                        fetch_redirect_response=False,
                    )
                    location = response["Location"]
                    self.assertTrue(location.startswith("/"))
                    self.assertFalse(location.startswith(("//", "/\\")))

    def test_unsafe_next_is_dropped_from_the_form_a_browser_submits(self):
        # The form's action has no query string, so a browser sends next only
        # through the hidden field: it must render empty for an unsafe value.
        for payload in UNSAFE_NEXTS:
            with self.subTest(payload=payload):
                self.client.logout()
                page = get_page(
                    self.client, f"{LOGIN_PATH}?{urlencode({'next': payload})}"
                )
                ((_, inputs),) = page.forms("main")
                next_values = [
                    a.get("value") for a in inputs if a.get("name") == "next"
                ]
                self.assertEqual(next_values, [""])

                response = self.client.post(
                    LOGIN_PATH,
                    {
                        "username": USERNAME,
                        "password": PASSWORD,
                        "next": next_values[0],
                    },
                )

                self.assertIn("_auth_user_id", self.client.session)
                self.assertRedirects(response, DASHBOARD, fetch_redirect_response=False)

    def test_next_cannot_inject_markup_into_the_login_page(self):
        script = "<script>alert(1)</script>"
        # Both payloads have no scheme or host, so url_has_allowed_host_and_scheme
        # accepts them as relative same-site paths and they reach the template:
        # only escaping keeps the markup inert.
        payloads = (f'">{script}', f'/x/?q=">{script}')
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.get(LOGIN_PATH, {"next": payload})

                self.assertNotContains(response, script)
        page = PageParser()
        page.feed(self.client.get(LOGIN_PATH, {"next": payloads[1]}).content.decode())
        ((_, inputs),) = page.forms("main")
        next_values = [a.get("value") for a in inputs if a.get("name") == "next"]
        self.assertEqual(next_values, [payloads[1]])


INVALID_LOGIN = (
    "Please enter a correct username and password. Note that both fields may be"
    " case-sensitive."
)


class LoginFailureTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user(USERNAME, password=PASSWORD)

    def test_failed_login_shows_one_generic_error(self):
        # Same message for a wrong password and an unknown username, so the page
        # doesn't reveal which usernames exist.
        cases = (
            ("wrong password", USERNAME, "Wrong-Pass-9!"),
            ("unknown username", "nobody", "Wrong-Pass-9!"),
        )
        main_texts = []
        for case, username, password in cases:
            with self.subTest(case=case):
                response = self.client.post(
                    LOGIN_PATH, {"username": username, "password": password}
                )

                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, "accounts/login.html")
                page = PageParser()
                page.feed(response.content.decode())
                self.assertIn(INVALID_LOGIN, page.text("main"))
                self.assertNotIn("_auth_user_id", self.client.session)
                self.assertNotContains(response, password)
                main_texts.append(page.text("main"))
        # Both cases must have run cleanly before their pages can be compared.
        self.assertEqual(len(main_texts), 2)
        self.assertEqual(main_texts[0], main_texts[1])

    def test_inactive_user_gets_the_generic_error(self):
        # The default ModelBackend rejects is_active=False before the form's
        # "This account is inactive." check, so the account isn't revealed.
        user = get_user_model().objects.get(username=USERNAME)
        user.is_active = False
        user.save()

        response = self.client.post(
            LOGIN_PATH, {"username": USERNAME, "password": PASSWORD}
        )

        page = PageParser()
        page.feed(response.content.decode())
        self.assertIn(INVALID_LOGIN, page.text("main"))
        self.assertNotIn("This account is inactive.", page.text("main"))
        self.assertNotIn("_auth_user_id", self.client.session)


class LoginLoggedInTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(USERNAME, password=PASSWORD)
        self.client.force_login(user)

    def test_logged_in_get_redirects_without_the_form(self):
        response = self.client.get(LOGIN_PATH)

        self.assertRedirects(response, DASHBOARD, fetch_redirect_response=False)
        self.assertTemplateNotUsed(response, "accounts/login.html")

    def test_logged_in_get_never_follows_an_unsafe_next(self):
        # The logged-in short-circuit (dispatch -> get_success_url) is a
        # separate path from form_valid, so pin its next check too.
        for payload in UNSAFE_NEXTS:
            with self.subTest(payload=payload):
                response = self.client.get(LOGIN_PATH, {"next": payload})

                self.assertRedirects(
                    response,
                    DASHBOARD,
                    fetch_redirect_response=False,
                )

    def test_logged_in_post_redirects_without_logging_in_again(self):
        # Empty data: a re-login with valid credentials would redirect to the
        # same place, so only the logged-in short-circuit can pass this.
        response = self.client.post(LOGIN_PATH, {})

        self.assertRedirects(response, DASHBOARD, fetch_redirect_response=False)
        self.assertTemplateNotUsed(response, "accounts/login.html")
        self.assertEqual(list(get_messages(response.wsgi_request)), [])
