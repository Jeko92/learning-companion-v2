# Review: setup-env-settings

## Verdict: FAIL

The FAIL comes from a high-severity finding: a `SECRET_KEY` that starts with `$` is expanded as a reference to another variable. Both reviewers reported this independently, and the main session reproduced it with dummy values.

All acceptance criteria are covered and the suite is green: 18 tests OK, and `ruff check` and `ruff format --check` are clean.

## Acceptance criteria
- AC1: covered by `test_env.test_secret_key_comes_from_environment`, `test_settings.test_secret_key_comes_from_resolve_settings` and `test_settings.test_generated_secret_key_is_not_hardcoded`. PASS, but see finding 2: the wiring tests are weak.
- AC2: covered by `test_env.test_missing_secret_key_raises_improperly_configured` and `test_env.test_empty_secret_key_raises_improperly_configured`. PASS, but a whitespace-only key isn't covered (finding 4).
- AC3: covered by `test_env.test_debug_is_parsed_as_boolean`. PASS.
- AC4: covered by `test_env.test_debug_defaults_to_false`. PASS.
- AC5: covered by `test_env.test_allowed_hosts_is_a_trimmed_comma_separated_list`. PASS.
- AC6: covered by `test_env.test_allowed_hosts_defaults_to_localhost`. PASS.
- AC7: covered by `test_env.test_values_come_from_env_file`. PASS.
- AC8: covered by `test_env.test_environment_wins_over_env_file`. PASS. Mutation-checked during implementation.
- AC9: covered by `test_env.test_missing_env_file_is_not_an_error`. PASS.
- AC10: covered by `test_env_example.test_defines_every_variable`, `test_each_variable_has_a_comment_above_it` and `test_debug_is_on_for_local_development`. PASS.

## Findings
1. **[high]** `src/config/env.py:29`. `env.str("SECRET_KEY")` goes through django-environ's proxy feature, which treats a value starting with `$` as the name of another variable. If no such variable exists, startup fails with `Set the <rest of the key> environment variable`. That puts most of the secret into tracebacks, CI output and hook logs. If a matching variable does exist, `SECRET_KEY` silently becomes that variable's value. Django's `get_random_secret_key`, which the README and `.env.example` tell people to use, can put `$` first, about 1 key in 50.
   - Reproduced: `{"SECRET_KEY": "$dummyval"}` raises `ImproperlyConfigured: Set the dummyval environment variable`, and `{"SECRET_KEY": "$OTHER", "OTHER": "swapped"}` resolves to `'swapped'`.
   - Recommendation: read `SECRET_KEY` literally (the raw value from the resolved mapping) with no proxy expansion, and add a test for a key starting with `$`.
   - The reviewers rated it medium. It's raised to high because the documented setup path triggers it and it can leak or replace the secret.
2. **[medium]** `src/config/tests/test_settings.py:14-15`. The wiring tests are nearly circular. They compare `settings` with `resolve_settings` run on the same `os.environ` and the developer's real `.env`, so a hardcoded `DEBUG = True` or `ALLOWED_HOSTS = ["localhost", "127.0.0.1"]` in `settings.py` would pass on a typical machine. The `DEBUG` test already passed by coincidence at step 11's red stage.
   - Recommendation: patch `os.environ` with distinctive values for all three variables, reload `config.settings`, assert on those values, and restore and reload in cleanup.
3. **[low]** `src/config/env.py:37-40`. `ALLOWED_HOSTS="a.com, "` gives `["a.com", ""]`. Recommendation: drop empty entries. `ALLOWED_HOSTS=""` (set but empty) then gives `[]`, which rejects every host when DEBUG is off. That fails closed and stays as is, but the docs should say so.
4. **[low]** `src/config/env.py:30`. A whitespace-only `SECRET_KEY` passes the empty check, which goes against the intent of AC2. Recommendation: reject a key that is empty after stripping whitespace.
5. **[low]** `src/config/tests/test_env_example.py:24-27`. If a variable is missing, `next(...)` with no default raises `StopIteration`, so the test errors instead of failing an assertion. Recommendation: give `next` a default and assert on it.
6. **[low]** `.env.example`. Lines django-environ can't parse (for example `SECRET_KEY = abc`, with spaces) are logged at WARNING with the whole line, value included, to stderr. And `DEBUG=True` is the copy-paste default. Recommendation: in `.env.example`, document "no spaces around `=`" and warn more strongly that `DEBUG=True` is for local development only.

Not adopted (recorded for later tickets):
- **[low]** No exact pins, lock file or hashes in `requirements.txt`. The project convention is version ranges. Revisit in `docker`/`ci-tests`.
- **[low]** No key-strength check when DEBUG is off. Better done as `manage.py check --deploy` in the `ci-tests`/`docker` tickets.
- **[low]** The old `django-insecure-...` dev key is still in the scaffold commit on `develop` and `main`. It can't be removed without rewriting history, which is forbidden. It was dev-only and must never be reused.

## Reviewed
commit 22fac90, 2026-10-01. Reviewers: `code-reviewer` (0 high, 2 medium, 4 low) and `security-reviewer` (0 high, 1 medium, 5 low). Main session: acceptance check, suite and lint, and reproduction of finding 1.
