"""Resolve environment-specific settings from the process environment and .env."""

import re
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import environ as django_environ
from django.core.exceptions import ImproperlyConfigured

DEFAULT_ALLOWED_HOSTS = ["localhost", "127.0.0.1"]
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
TRUE_VALUES = frozenset({"true", "1", "yes", "on"})
FALSE_VALUES = frozenset({"false", "0", "no", "off"})
# An hour to start with: HSTS is sticky in browsers, so raise it once HTTPS
# is known to work.
DEFAULT_HSTS_SECONDS = 3600


@dataclass(frozen=True)
class EnvSettings:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]
    openai_api_key: str
    openai_model: str
    # None when DATABASE_URL is unset or blank: settings.py keeps its default.
    database: dict | None
    csrf_trusted_origins: list[str]
    ssl_redirect: bool
    session_cookie_secure: bool
    csrf_cookie_secure: bool
    hsts_seconds: int


def trimmed_list(env: django_environ.Env, name: str, default: list[str]) -> list[str]:
    """A comma-separated list, each entry trimmed, empty entries dropped."""
    return [entry.strip() for entry in env.list(name, default=default) if entry.strip()]


def csrf_trusted_origins(env: django_environ.Env) -> list[str]:
    origins = trimmed_list(env, "CSRF_TRUSTED_ORIGINS", default=[])
    if not all(origin.startswith(("http://", "https://")) for origin in origins):
        raise ImproperlyConfigured(
            "The CSRF_TRUSTED_ORIGINS environment variable must list "
            "origins that start with http:// or https://"
        )
    return origins


def database_config(env: django_environ.Env) -> dict | None:
    """DATABASE_URL parsed by django-environ, which only warns about a value
    it can't parse (or accepts an unknown scheme as an engine) and leaves
    Django to fail at the first query. The error names the variable, never
    the value: a URL can carry a password."""
    raw = env.ENVIRON.get("DATABASE_URL", "").strip()
    if not raw:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            config = env.db_url_config(raw)
    except ValueError:
        # Its message quotes part of the URL (e.g. "as 'pa'" for a password
        # with an unencoded "/"), so it is dropped, not chained.
        config = {}
    if config.get("ENGINE") not in env.DB_SCHEMES.values():
        raise ImproperlyConfigured(
            "The DATABASE_URL environment variable is not a valid database URL"
        ) from None
    return config


def optional_bool(env: django_environ.Env, name: str, default: bool) -> bool:
    """A strict boolean: set but blank means the default, like unset. Unlike
    env.bool(), which reads anything unknown as False, a value that isn't
    clearly true or false is an error, so a typo can't quietly turn a
    security setting off."""
    raw = env.ENVIRON.get(name, "").strip().lower()
    if not raw:
        return default
    if raw in TRUE_VALUES:
        return True
    if raw in FALSE_VALUES:
        return False
    raise ImproperlyConfigured(f"The {name} environment variable must be true or false")


def optional_non_negative_int(env: django_environ.Env, name: str, default: int) -> int:
    """A whole number, 0 or more (ASCII digits only); set but blank means the
    default, like unset."""
    raw = env.ENVIRON.get(name, "").strip()
    if not raw:
        return default
    if not re.fullmatch(r"[0-9]+", raw):
        raise ImproperlyConfigured(
            f"The {name} environment variable must be a whole number of "
            "seconds, 0 or more"
        )
    return int(raw)


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
    debug = env.bool("DEBUG", default=False)
    return EnvSettings(
        secret_key=required_raw(Env.ENVIRON, "SECRET_KEY"),
        debug=debug,
        allowed_hosts=trimmed_list(env, "ALLOWED_HOSTS", default=DEFAULT_ALLOWED_HOSTS),
        openai_api_key=required_raw(Env.ENVIRON, "OPENAI_API_KEY"),
        # Set but blank means the default, like unset.
        openai_model=Env.ENVIRON.get("OPENAI_MODEL", "").strip()
        or DEFAULT_OPENAI_MODEL,
        database=database_config(env),
        csrf_trusted_origins=csrf_trusted_origins(env),
        # The HTTPS settings are on in production (DEBUG off) unless the
        # environment says otherwise.
        ssl_redirect=optional_bool(env, "SECURE_SSL_REDIRECT", default=not debug),
        session_cookie_secure=optional_bool(
            env, "SESSION_COOKIE_SECURE", default=not debug
        ),
        csrf_cookie_secure=optional_bool(env, "CSRF_COOKIE_SECURE", default=not debug),
        hsts_seconds=optional_non_negative_int(
            env, "SECURE_HSTS_SECONDS", default=0 if debug else DEFAULT_HSTS_SECONDS
        ),
    )
