# Review: docker

## Verdict: FAIL

Two confirmed defects block the ticket.

1. **`DATABASE_URL` leaks part of the URL (AC1).** A malformed URL makes django-environ raise a raw `ValueError` that echoes part of the URL, a password fragment included. AC1 requires a fixed `ImproperlyConfigured` naming the variable.
2. **The documented run command fails.** `.env.example`'s blank `DATABASE_URL=` line, copied into `.env` and passed with `docker run --env-file .env`, overrides the image's `DATABASE_URL`. The container then can't start (AC7/AC12).

The healthcheck also goes unhealthy with the custom `ALLOWED_HOSTS` the README suggests. The image itself, the static file serving and the smoke check work: the suite is green, a no-cache build succeeds, and the smoke script passes all 13 checks. The findings below are new plan steps 13–17.

## Acceptance criteria
- AC1: `config.tests.test_env` (`test_database_*`, `test_an_unparseable_database_url_raises_improperly_configured`) and `config.tests.test_settings` (`test_the_database_comes_from_database_url`, `test_a_blank_database_url_keeps_the_sqlite_file_in_src`). **FAIL**: `postgres://u:pw@host:abc/db` and `postgres://u:pa/ss@db/x` raise `ValueError: Port could not be cast to integer value as 'abc'` / `'pa'`, reproduced in the main session. That is not the fixed `ImproperlyConfigured`, and the second leaks part of the password.
- AC2: covered by `test_env` (`test_csrf_trusted_origins_*`, `test_a_csrf_trusted_origin_without_http_or_https_raises`) and `test_settings` (`test_csrf_trusted_origins_*`). PASS
- AC3: covered by `config.tests.test_env_example`. PASS for the criterion as written, but its blank `DATABASE_URL=` line breaks the container (finding 2).
- AC4: covered by `test_settings.StaticFilesSettingsTests` and `config.tests.test_static_files` (gzip served after `collectstatic`, plain names, no missing-directory warning). The filter was proven by mutation: removing it turns `MissingStaticRootTests` red. PASS
- AC5: covered by `config.tests.test_docker.RequirementsTests`. PASS
- AC6: covered by `DockerfileTests`. A `docker build --no-cache` from `6fd012b` succeeded (the Tailwind binary downloaded and the CSS built).
  - The final image's `Config.Env` and `docker history` contain neither `SECRET_KEY` nor `OPENAI_API_KEY`.
  - The user is `app`, the volume is `/app/data` (owned by `app`), and `/app/src` is root-owned.
  - `src/staticfiles` holds `css/tailwind.css` and `.gz` copies. The image is 359 MB.

  PASS
- AC7: covered by `EntrypointTests` and the smoke checks (healthy after migrate, missing `SECRET_KEY` exits non-zero and names it, `docker stop` exits 0). **FAIL** on the documented `--env-file .env` path (finding 2).
- AC8: covered by `DockerfileTests.test_the_healthcheck_requests_the_favicon_with_python` and the smoke script's wait for healthy. PASS as specified; see finding 3 for custom `ALLOWED_HOSTS`.
- AC9: covered by `DockerignoreTests`. PASS (finding 4 widens it).
- AC10: `scripts/docker-smoke.sh` passed all 13 checks in the main session on `6fd012b` and left no container, volume or image behind. PASS
- AC11: the suite runs 572 tests OK, without Docker and without the WhiteNoise warning. Lint is clean, there are no migrations, and the default database dict is unchanged (`test_a_blank_database_url_keeps_the_sqlite_file_in_src`). PASS
- AC12: `README.md` "Run with Docker" and `CLAUDE.md` updated. **FAIL** in substance: the first documented command fails with a `.env` made from `.env.example`, it can carry `DEBUG=True`, and the `ALLOWED_HOSTS` advice breaks the healthcheck (findings 2, 3, 5).

## Findings
- [medium] `src/config/env.py` (`database_config`): `env.db_url_config()` raises `ValueError` for a non-integer port, including a password containing an unencoded `/`, `#` or `?`. The message echoes part of the URL, which breaks AC1's fixed message and its never-echo guarantee; it would show up in the container's start-up traceback and logs. Recommendation: catch the parse error and raise the fixed `ImproperlyConfigured … from None`, with both URLs as test cases. Plan step 13.
- [medium] `.env.example` and the documented `docker run --env-file .env`: a `.env` copied from `.env.example` carries `DATABASE_URL=` (blank). A blank `--env-file` line overrides the image's `ENV DATABASE_URL` (verified with `docker run --env-file`), so the app falls back to `/app/src/db.sqlite3` in a root-owned directory, and `migrate` fails. Recommendation:
  - document `DATABASE_URL` in `.env.example` as a commented-out example (a deliberate change to `test_env_example.py`'s rule for optional variables);
  - add a smoke check that runs the image with an env file made from `.env.example`.

  Plan steps 14 and 15.
- [medium] `Dockerfile` `HEALTHCHECK` with README's `-e ALLOWED_HOSTS=...`: the check sends `Host: 127.0.0.1`. If `ALLOWED_HOSTS` leaves it out, Django answers 400 and the container stays unhealthy for good. Recommendation: document that `ALLOWED_HOSTS` must keep `127.0.0.1` (show it in the example), in the README, the Dockerfile comment and `CLAUDE.md`. Plan step 15.
- [low] `.dockerignore`: `.env` only matches the root file, but `.gitignore` ignores `.env` at any depth, so a nested `src/.env` or a `.env.local` would reach the image through `COPY src/ src/`. Recommendation: `**/.env` and `**/.env.*`. Plan step 16.
- [low] README, Dockerfile header and `CLAUDE.md` run commands: `--env-file .env` from `.env.example` carries `DEBUG=True`, and `-p 8000:8000` publishes on every interface, so debug pages are reachable from the LAN. Recommendation: show `-e DEBUG=False` (which beats `--env-file`) and `-p 127.0.0.1:8000:8000` in the documented commands. Plan step 15.
- [low] `src/config/tests/test_docker.py` (`test_the_build_stage_installs_requirements_builds_css_and_collects`): swapping `tailwind build` and `collectstatic`, which would collect without the CSS, still passes. Recommendation: assert the order. Plan step 17.
- [low] `scripts/docker-smoke.sh` (`home_page_is_served`): `curl … | grep -q` under `pipefail` can fail spuriously if `grep` exits before curl has finished writing. Recommendation: capture the body first. Plan step 15.
- [low] `Dockerfile`: `HEALTHCHECK --start-interval` needs Docker Engine 25 or newer. Recommendation: say so in the README. Plan step 15.
- [low] `Dockerfile` `CMD`: a single sync worker by default, so one slow AI call blocks every other request. `WEB_CONCURRENCY` is documented. Accepted as a design choice, no action.
- [info, for #36] Behind an HTTPS proxy the README relies on `CSRF_TRUSTED_ORIGINS`. #36 should set `SECURE_PROXY_SSL_HEADER` (and gunicorn's `--forwarded-allow-ips`), and may reject `http://` origins once HTTPS is required. Wildcards like `https://*.example` pass the scheme check, which is Django's own behaviour.
- Security review: high 0, medium 0, low 2 (the `ValueError` leak and the `DEBUG` run command, both above), info 3 (the nested `.env`, the blank `DATABASE_URL` and the #36 note, all above).

## Reviewed
commit 6fd012b, 2026-10-04 (base 09e62ed)
