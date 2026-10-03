# Review: ai-client
## Verdict: PASS

No high or medium findings from either reviewer, every acceptance criterion is covered by a passing test, and the suite, lint and migration check are green. Six low findings are recorded below; two of them are follow-ups for #16/#17.

## Acceptance criteria
- AC1 — `ResolveSettingsTests.test_a_missing_or_blank_openai_api_key_raises_improperly_configured` (fixed message, no value), `test_openai_api_key_starting_with_dollar_is_used_literally` — PASS
- AC2 — `ResolveSettingsTests.test_openai_model_defaults_to_gpt_4_1_mini`, `test_openai_model_is_trimmed` — PASS
- AC3 — `ResolveSettingsTests.test_openai_api_key_from_environment_wins_over_env_file`, `test_openai_model_from_environment_wins_over_env_file`, `test_does_not_mutate_the_given_mapping_or_os_environ`; `SettingsWiringTests.test_openai_api_key_comes_from_the_environment`, `test_openai_model_comes_from_the_environment`, `test_openai_model_defaults_when_blank`, `test_no_openai_key_is_hardcoded` — PASS
- AC4 — `EnvExampleTests` (every variable defined with a comment above, `test_the_openai_key_is_an_obvious_placeholder`, `test_the_openai_model_shows_the_default`) — PASS
- AC5 — `AiAppTests.test_the_openai_sdk_is_a_range_pinned_requirement` — PASS
- AC6 — `AiAppTests.test_ai_app_is_installed`, `CompleteTests.test_the_reply_text_comes_back_trimmed` — PASS
- AC7 — `GetClientTests.test_the_client_uses_the_key_a_30_second_timeout_and_2_retries`, `CompleteTests.test_one_request_with_the_model_and_the_system_then_user_message` — PASS
- AC8 — `CompleteErrorTests.test_every_sdk_error_becomes_one_safe_ai_service_error` (five SDK error types, safe message, `__cause__`, no key) — PASS
- AC9 — `CompleteErrorTests.test_each_failure_is_logged_once_by_type_without_the_key` (no key, no SDK text, no `exc_info`) — PASS
- AC10 — `CompleteEmptyReplyTests.test_a_reply_without_content_is_an_ai_service_error` (no choices, `None`, blank) — PASS
- AC11 — `NoNetworkTestCase` (fails any real `OpenAI` construction), `GetClientTests.test_a_real_client_is_never_built_in_tests`; all service tests replace `get_client` — PASS
- AC12 — `CLAUDE.md` (Stack settings and OpenAI bullets, Commands, Layout) and `README.md` (Setup, variable table, Layout) updated (docs, no test) — PASS

Full suite (379 tests) green, ruff check and format clean, `makemigrations --check` reports no changes.

## Findings
- [low, follow-up for #16/#17] src/ai/services.py:45-47 — `raise AIServiceError(...) from error` keeps the SDK error as `__cause__` (AC8 requires it). If a caller lets `AIServiceError` escape, Django's 500 logging, the DEBUG page or an admin error mail would print the chained traceback, including the authentication error's text, which echoes the key's last characters. — Every view in #16/#17 must catch `AIServiceError` and show its message, pinned by a view test that the 500 path is never reached. (Security review. `OPENAI_API_KEY` itself is hidden on the debug page: it matches `SafeExceptionReporterFilter`'s `API|KEY` pattern.)
- [low, follow-up for #16/#17] src/ai/services.py:11-13 — the 30 s is per network phase (connect, write, each read), not per call, and the SDK honours a server's `Retry-After` up to 120 s (`openai/_constants.py:13`, verified). With 2 retries one `complete()` can hold a worker for minutes, and nothing rate-limits users yet. The docs' "30-second timeout" reads as a total bound. — When #16/#17 put the call behind a user action, decide on an overall deadline or fewer retries, and reword the docs to "30 s per network phase, 2 retries". (Security review.)
- [low] src/ai/services.py:56 — a malformed reply object (a choice without `.message`, `choices=None`) would raise `AttributeError`/`TypeError` outside `AIServiceError`. The SDK's typed models make this unlikely. — Optionally extract the text inside the `try` or catch those two, with a test row in `CompleteEmptyReplyTests`.
- [low, no change] src/config/env.py `required_raw` — a padded key (`"sk-x "`, a CRLF `\r`) is returned unstripped. That is AC1's "read literally" and matches `SECRET_KEY`; a bad key surfaces as an `AIServiceError` at request time.
- [low, no change] src/ai/tests/test_services.py — `test_a_real_client_is_never_built_in_tests` partly re-tests `NoNetworkTestCase`'s own guard; it pins the guard deliberately (AC11).
- [low, no change] src/config/tests/test_settings.py — the cleanup reload needs `OPENAI_API_KEY` in the real environment or `.env`; without it the whole suite already fails at settings import, as documented.

Verified as not findings: no hardcoded key (`.env.example` holds only `sk-dummy`, `.env` is git-ignored); `ImproperlyConfigured` names the variable, never the value; the error tests would catch dropping `from error` (`__cause__ is error`) and switching to `logger.exception` (`exc_info is None`); a test that forgets to patch `get_client` fails loudly (the guard's `AssertionError` is not an `OpenAIError`); the `openai>=3.24,<3.25` pin matches the repo's style.

## Reviewed
commit de99634, 2026-10-03 (base 1b0398d)
