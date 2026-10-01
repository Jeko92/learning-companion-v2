# Plan: setup-env-settings

## Research summary
- **Project:** a scaffold with no tests yet. `config` is the only package under `src/` and has an `__init__.py`. `src/` itself has none. `BASE_DIR = Path(__file__).resolve().parent.parent` is `src/`, so the repo-root `.env` is `BASE_DIR.parent / ".env"`. `settings.py` imports only `pathlib.Path`, hardcodes `SECRET_KEY`, and has `DEBUG = True`, `ALLOWED_HOSTS = []`.
- **Test discovery:** `manage.py test src` finds `test*.py` only inside packages. `src/config/tests/` needs an `__init__.py`, after which modules import as `config.tests.test_<x>`. Run one module with `./.venv/bin/python src/manage.py test config.tests.test_env --verbosity 2`.
- **Hooks:** they run `manage.py test src --verbosity 0` and `ruff check .`, set no env vars, and load no `.env`. Once `SECRET_KEY` is required, every hook test run, and therefore every commit, needs a local `.env` or an exported `SECRET_KEY`.
- **Ruff:** defaults (88 columns, E4/E7/E9/F), `target-version = "py314"`, migrations excluded.
- **django-environ 0.14.0**, already in `.venv` but not yet in `requirements.txt`:
  - `read_env` silently skips a missing file.
  - With `overwrite=False` it uses `setdefault`, so values already set in the environment win. It writes into the class attribute `Env.ENVIRON`, which is `os.environ`.
  - `bool`: `int(v) != 0` first, then `v.lower().strip() in ('true','on','ok','y','yes','1')`.
  - `list`: splits on commas and **does not trim whitespace**.
  - A missing required var raises `ImproperlyConfigured("Set the SECRET_KEY environment variable")`. An **empty string is returned as `''`**, not rejected.
  - `ENVIRON` is read on every call, with no caching.
  - Metadata lists Django up to 6.0, not 6.1. It works in this venv, but that's unconfirmed upstream.
- **Docs:** `README.md` has `## Setup` (venv, pip install, migrate, runserver) and `## Tests and lint`. `CLAUDE.md` has the setup command block.

## Design decisions
- **Resolution is a pure function** in `src/config/env.py`: `resolve_settings(environ: Mapping[str, str], env_file: Path) -> EnvSettings`. `EnvSettings` is a small frozen dataclass with `secret_key`, `debug` and `allowed_hosts`. Tests pass a plain dict and a temp file, so they never depend on the developer's real `.env` or `os.environ`.
- **No global mutation:** `resolve_settings` works on a copy of `environ` and never writes to `os.environ`. That's the reason not to call `Env.read_env` on the default class. It also keeps tests independent of each other.
- **Precedence (AC8):** `.env` values only fill in keys that aren't already set, matching `read_env(overwrite=False)` semantics.
- **Own handling where the library falls short:** we strip whitespace from `ALLOWED_HOSTS` entries (AC5), and we treat an empty `SECRET_KEY` as missing, raising `ImproperlyConfigured` that names `SECRET_KEY` (AC2).
- **`settings.py` stays thin:** it calls `resolve_settings(os.environ, BASE_DIR.parent / ".env")` and assigns the three values. Nothing else in `settings.py` changes.
- **Dependency:** `django-environ>=0.14,<0.15` goes in `requirements.txt`, pinned to the minor version we checked, because Django 6.1 isn't officially declared.
- **Local `.env` before wiring:** before step 11 (the one that makes `SECRET_KEY` required at startup), create a local, git-ignored `.env` from `.env.example` with a freshly generated key. Otherwise the hooks' suite run goes red and blocks commits. The `.env` is never committed.

## Steps
Tests use `django.test.SimpleTestCase`. Steps 1–8 test `resolve_settings` directly with dict mappings and `tempfile` `.env` files.

- [x] 1. `resolve_settings` returns the `SECRET_KEY` from the mapping. Test: `src/config/tests/test_env.py` (plus `src/config/tests/__init__.py`). Impl: `src/config/env.py`, `requirements.txt` (add `django-environ`). Covers: AC1 (resolution part).
- [x] 2. A missing **or empty** `SECRET_KEY` raises `ImproperlyConfigured`, and the message contains `SECRET_KEY`. Test: `test_env.py`, one test for missing and one for empty. The empty case is the one expected to be red, because the library returns `''`. Impl: `env.py`. Covers: AC2.
- [x] 3. `DEBUG` parses as a boolean. `True`/`1`/`yes` give `True`, and `False`/`0`/`no` give `False`. Test: `test_env.py`. Impl: `env.py`. Covers: AC3.
- [x] 4. If `DEBUG` is unset, `debug` is `False`. Test: `test_env.py`. Impl: none. Covers: AC4.
  - Changed during implementation (approved 2026-10-01): step 3 couldn't stay green without `default=False`, because step 1's test doesn't set `DEBUG`. So this is a guard test that passes on arrival, not a red–green cycle.
- [x] 5. `ALLOWED_HOSTS="example.com, www.example.com"` gives `["example.com", "www.example.com"]`. Test: `test_env.py`. Impl: `env.py`, with an unset default of `[]` (today's value), so that step 6 is a real red–green cycle. Covers: AC5.
- [x] 6. If `ALLOWED_HOSTS` is unset, `allowed_hosts` is `["localhost", "127.0.0.1"]`. Test: `test_env.py`. Impl: `env.py`. Covers: AC6.
- [x] 7. Values from the `env_file` are used when the mapping doesn't contain them. Test: `test_env.py`, with a temp `.env` holding `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` and an empty mapping. Impl: `env.py`. Covers: AC7.
  - AC9 gets a guard test in this step's refactor phase: a nonexistent `env_file` plus a mapping with `SECRET_KEY` resolves without error. It is expected to pass straight away, because `read_env` skips missing files. It's a regression guard, so the step records it as green-on-arrival rather than a red–green cycle.
- [x] 8. When a key is in both the mapping and the `env_file`, the mapping's value wins. Test: `test_env.py`. Impl: none. Covers: AC8.
  - Changed during implementation: step 7's `read_env(overwrite=False)` already gives this precedence, so this is a guard test that passes on arrival. It's handled the same way as step 4, per the user's decision there. A temporary mutation to `overwrite=True` made it fail, then was reverted, which confirms the guard catches a regression.
- [ ] 9. `resolve_settings` doesn't modify the mapping it's given or `os.environ`. Test: `test_env.py`, which passes a dict and a temp `.env` and asserts that the dict and `os.environ` are unchanged afterwards. Impl: `env.py` (only if the step 7/8 implementation leaked). Covers: the design decision behind AC8/AC9 test isolation. If this test passes straight away, record it as a guard, the same way as AC9.
- [ ] 10. `.env.example` at the repo root defines `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS`, has a comment line before each, and sets `DEBUG=True`. Test: `src/config/tests/test_env_example.py`, which parses the file from `settings.BASE_DIR.parent`. Impl: `.env.example`, not under `src/`. Covers: AC10.
  - After this step, and before step 11: copy `.env.example` to `.env` locally, put in a generated key, and don't commit it. Generate the key with `./.venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`.
- [ ] 11. `settings.py` takes its values from `resolve_settings`. `settings.SECRET_KEY`, `settings.DEBUG` and `settings.ALLOWED_HOSTS` equal `resolve_settings(os.environ, BASE_DIR.parent / ".env")`, and `src/config/settings.py` no longer contains the string `django-insecure`. Test: `src/config/tests/test_settings.py`. Impl: `src/config/settings.py`. Covers: AC1 (wiring and removal of the hardcoded key).
  - The test compares `SECRET_KEY` and `ALLOWED_HOSTS` on `django.conf.settings`. Django's test runner forces `DEBUG=False` at run time, so `DEBUG` is checked by reading the `config.settings` module attribute, not `django.conf.settings`.
- [ ] 12. Docs. `README.md` `## Setup` gains "copy `.env.example` to `.env`, set `SECRET_KEY`" with the key-generation command, placed before `migrate`. `CLAUDE.md` gets the same in the setup command block, and its Stack section notes that settings come from `.env` via `django-environ`. No test, as the ticket notes. Commit as `docs(setup-env-settings): ...`.

## Coverage
| AC | Steps |
|---|---|
| AC1 | 1, 11 |
| AC2 | 2 |
| AC3 | 3 |
| AC4 | 4 |
| AC5 | 5 |
| AC6 | 6 |
| AC7 | 7 |
| AC8 | 8 (isolation guard in 9) |
| AC9 | 7 (guard test) |
| AC10 | 10 |
| Docs (ticket notes) | 12 |
