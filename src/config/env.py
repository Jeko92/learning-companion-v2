"""Resolve environment-specific settings from the process environment and .env."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import environ as django_environ
from django.core.exceptions import ImproperlyConfigured

DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1"]


@dataclass(frozen=True)
class EnvSettings:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]


def resolve_settings(environ: Mapping[str, str], env_file: Path) -> EnvSettings:
    # read_env is a classmethod that writes into cls.ENVIRON, so give it a
    # private copy instead of the default os.environ.
    class Env(django_environ.Env):
        ENVIRON: ClassVar[dict[str, str]] = dict(environ)

    Env.read_env(env_file)
    env = Env()
    # Read the raw value: env.str() would expand a leading "$" as a reference
    # to another variable, and generated keys can start with "$".
    secret_key = Env.ENVIRON.get("SECRET_KEY", "")
    if not secret_key.strip():
        raise ImproperlyConfigured(
            "The SECRET_KEY environment variable must be set and not empty"
        )
    return EnvSettings(
        secret_key=secret_key,
        debug=env.bool("DEBUG", default=False),
        allowed_hosts=[
            host.strip()
            for host in env.list("ALLOWED_HOSTS", default=DEFAULT_ALLOWED_HOSTS)
        ],
    )
