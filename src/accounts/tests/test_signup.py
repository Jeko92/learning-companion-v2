from django.test import TestCase
from django.urls import URLResolver, get_resolver, reverse

from accounts import urls as accounts_urls

SIGNUP_PATH = "/accounts/signup/"


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
