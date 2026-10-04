import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

# Production-like: DEBUG off, a key long and varied enough for
# security.W009, and every HTTPS variable blank (the default, which also beats
# a developer's .env).
DEPLOY_ENVIRON = {
    "DEBUG": "False",
    "SECRET_KEY": "deploy-check-dummy-key-0123456789-abcdefghijklmnopqrstuvwxyz",
    "OPENAI_API_KEY": "sk-deploy-check",
    "SECURE_SSL_REDIRECT": "",
    "SESSION_COOKIE_SECURE": "",
    "CSRF_COOKIE_SECURE": "",
    "SECURE_HSTS_SECONDS": "",
    "SECURE_PROXY_SSL_HEADER": "",
}


class DeployCheckTests(SimpleTestCase):
    """Runs manage.py in a fresh process, so the settings are the ones a
    production start-up computes, not the test run's overrides."""

    def test_check_deploy_passes_with_the_default_production_settings(self):
        result = subprocess.run(
            [
                sys.executable,
                str(settings.BASE_DIR / "manage.py"),
                "check",
                "--deploy",
                "--fail-level",
                "WARNING",
            ],
            env={**os.environ, **DEPLOY_ENVIRON},
            capture_output=True,
            text=True,
            timeout=60,
            # The exit status is asserted below, with the output as message.
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
