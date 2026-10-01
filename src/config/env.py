"""Resolve environment-specific settings from the process environment and .env."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import environ as django_environ
from django.core.exceptions import ImproperlyConfigured

DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


@dataclass(frozen=True)
class EnvSettings:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]


def resolve_settings(environ: Mapping[str, str], env_file: Path) -> EnvSettings:
    env = django_environ.Env()
    env.ENVIRON = dict(environ)
    secret_key = env.str("SECRET_KEY")
    if not secret_key:
        raise ImproperlyConfigured(
            "The SECRET_KEY environment variable must not be empty"
        )
    return EnvSettings(
        secret_key=secret_key,
        debug=env.bool("DEBUG", default=False),
        allowed_hosts=[
            host.strip()
            for host in env.list("ALLOWED_HOSTS", default=DEFAULT_ALLOWED_HOSTS)
        ],
    )
