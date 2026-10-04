# Review: docker

## Verdict: PASS

This is a re-review after the FAIL of 2026-10-04 (base `b9c6c6a`, the `docs(docker): review findings` commit), covering plan steps 13–17. All earlier findings are resolved.
- The `DATABASE_URL` parse error no longer quotes the URL.
- `.env.example` no longer blanks out the image's `DATABASE_URL` through `--env-file`, and the smoke script now runs the image that way.
- The run commands keep `DEBUG` off and publish on `127.0.0.1`.
- The healthcheck's `ALLOWED_HOSTS` requirement and the Docker 25 requirement are documented.
- `.env` files at any depth stay out of the image.
- The build order is asserted.

The security re-review found nothing. The code re-review left three low findings, which don't block. Suite: 574 tests OK. Lint is clean, there are no migrations, and the smoke script passes all 17 checks.

## Acceptance criteria
- AC1: covered by `config.tests.test_env` (`test_database_*`, and `test_an_unparseable_database_url_raises_improperly_configured`, which now includes a non-integer port and a password with an unencoded `/`, and asserts no `__cause__` and a suppressed context) and `config.tests.test_settings` (`test_the_database_comes_from_database_url`, `test_a_blank_database_url_keeps_the_sqlite_file_in_src`). Both reviewers traced django-environ's `db_url_config`: every path that can quote the URL raises a `ValueError` or a subclass, and that is now dropped. PASS
- AC2: covered by `test_env` (`test_csrf_trusted_origins_*`, `test_a_csrf_trusted_origin_without_http_or_https_raises`) and `test_settings` (`test_csrf_trusted_origins_*`). PASS
- AC3: covered by `config.tests.test_env_example`. `DATABASE_URL` is now a commented-out example (`COMMENTED_EXAMPLES`, `test_database_url_is_only_a_commented_out_example`); the code reviewer judged that narrowing fair. PASS
- AC4: covered by `test_settings.StaticFilesSettingsTests` and `config.tests.test_static_files`. PASS
- AC5: covered by `config.tests.test_docker.RequirementsTests`. PASS
- AC6: covered by `DockerfileTests`, now including the build order, which was proven by a temporary mutation that swapped `tailwind build` and `collectstatic` and turned the test red. The first review's no-cache build and image inspection still apply: no key in the image config or history, `app` user, `/app/data` owned by `app`, root-owned `/app/src`, and compressed static files. Only comments changed in the `Dockerfile` since. PASS
- AC7: covered by `EntrypointTests` and the smoke checks: healthy after migrate, missing `SECRET_KEY` exits non-zero and names it, `docker stop` exits 0, and now a container started with `--env-file` (a `.env` built from `.env.example`) becomes healthy.
  - Regression check in the main session: the same image started with an env file containing a blank `DATABASE_URL=` exits 1 with `sqlite3.OperationalError: unable to open database file`. The new smoke check would therefore have caught the original defect.

  PASS
- AC8: covered by `DockerfileTests.test_the_healthcheck_requests_the_favicon_with_python` and the smoke script's waits for healthy. The `127.0.0.1` requirement for a custom `ALLOWED_HOSTS` is documented in the README, the `Dockerfile` comment and `CLAUDE.md`. PASS
- AC9: covered by `DockerignoreTests`, now including `**/.env` and `**/.env.*`. A throwaway build in the main session confirmed that the root `.env`, `src/.env`, `.env.local` and `.env.example` are excluded while other files are kept. PASS
- AC10: `scripts/docker-smoke.sh` passed all 17 checks on `5e7db29` and left no container, volume or image behind. The new checks cover the `.env.example`/`--env-file` path, `-e DEBUG=False` beating `DEBUG=True`, and log-in on the shared volume. PASS
- AC11: the suite runs 574 tests OK without Docker and without the WhiteNoise warning. Lint is clean, there are no migrations, and the default database is unchanged. PASS
- AC12: the README "Run with Docker" section and `CLAUDE.md` now document:
  - the safe run command (`-e DEBUG=False`, `-p 127.0.0.1:8000:8000`);
  - why `DATABASE_URL` is commented out;
  - the healthcheck's `127.0.0.1` requirement and the Docker 25 requirement.

  PASS

## Findings
Previous findings (review of `6fd012b`), all resolved:
- [medium] `DATABASE_URL` `ValueError` leak: resolved by step 13.
- [medium] blank `DATABASE_URL` in `.env.example` overriding the image through `--env-file`: resolved by steps 14 and 15.
- [medium] healthcheck with a custom `ALLOWED_HOSTS`: resolved by documentation in step 15.
- [low] nested `.env` files in the build context: resolved by step 16.
- [low] `DEBUG=True` and the port on all interfaces in the run commands: resolved by step 15.
- [low] build order not asserted: resolved by step 17.
- [low] `curl | grep` under `pipefail`: resolved by step 15.
- [low] Docker 25 requirement undocumented: resolved by step 15.
- [low] a single gunicorn worker by default: accepted earlier as a design choice (`WEB_CONCURRENCY`).
- [info, for #36] `SECURE_PROXY_SSL_HEADER` and gunicorn `--forwarded-allow-ips` behind an HTTPS proxy: still for #36.

New (all low, non-blocking):
- [low] `scripts/docker-smoke.sh` (`debug_is_off`): it passes for any body without "URLconf", so an empty or non-404 reply would pass too. It is called right after the container reports healthy, on the port read back from that container, so a 404 page is what comes back. Recommendation: when the script next changes, also assert the 404 status and a non-empty body. No action now.
- [low] `src/config/tests/test_docker.py` (`test_the_smoke_script_runs_the_image_with_an_env_file_from_the_example`): it is a presence check of two substrings, which is acceptable because the script itself can't run in the suite. No action.
- [low] `src/config/tests/test_env_example.py`: the commented example's value is pinned to an exact string, deliberately. No action.
- Security re-review: no findings (high 0, medium 0, low 0, info 0). The temporary env file lives in the `mktemp -d` directory and is removed by the `EXIT` trap, and `check()` prints only check names.

## Reviewed
commit 5e7db29, 2026-10-04 (base b9c6c6a, re-review)
