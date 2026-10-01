"""Resolve environment-specific settings from the process environment and .env."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import environ as django_environ


@dataclass(frozen=True)
class EnvSettings:
    secret_key: str
    debug: bool
    allowed_hosts: list[str]


def resolve_settings(environ: Mapping[str, str], env_file: Path) -> EnvSettings:
    env = django_environ.Env()
    env.ENVIRON = dict(environ)
    return EnvSettings(secret_key=env.str("SECRET_KEY"), debug=False, allowed_hosts=[])
