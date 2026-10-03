"""Resolve environment-specific settings from the process environment and .env."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import environ as django_environ
from django.core.exceptions import ImproperlyConfigured

DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class EnvSettings:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]
    openai_api_key: str
    openai_model: str


def required_raw(environ: Mapping[str, str], name: str) -> str:
    """A required secret, read raw: env.str() would expand a leading "$" as a
    reference to another variable, and generated keys can start with "$".
    The error names the variable, never the value."""
    value = environ.get(name, "")
    if not value.strip():
        raise ImproperlyConfigured(
            f"The {name} environment variable must be set and not empty"
        )
    return value


def resolve_settings(environ: Mapping[str, str], env_file: Path) -> EnvSettings:
    # read_env is a classmethod that writes into cls.ENVIRON, so give it a
    # private copy instead of the default os.environ.
    class Env(django_environ.Env):
        ENVIRON: ClassVar[dict[str, str]] = dict(environ)

    Env.read_env(env_file)
    env = Env()
    return EnvSettings(
        secret_key=required_raw(Env.ENVIRON, "SECRET_KEY"),
        debug=env.bool("DEBUG", default=False),
        allowed_hosts=[
            host.strip()
            for host in env.list("ALLOWED_HOSTS", default=DEFAULT_ALLOWED_HOSTS)
            if host.strip()
        ],
        openai_api_key=required_raw(Env.ENVIRON, "OPENAI_API_KEY"),
        # Set but blank means the default, like unset.
        openai_model=Env.ENVIRON.get("OPENAI_MODEL", "").strip()
        or DEFAULT_OPENAI_MODEL,
    )
