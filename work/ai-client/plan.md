# Plan: ai-client

## Research summary

- **Env settings** (`config/env.py`): `resolve_settings(environ, env_file) -> EnvSettings` (frozen dataclass: `secret_key`, `debug`, `allowed_hosts`). A private `Env` subclass gets a copy of the given mapping as `ENVIRON`, `read_env` fills only unset keys (environment beats `.env`), a missing `.env` is fine. `SECRET_KEY` is read raw (`Env.ENVIRON.get`, so a leading `$` isn't expanded) and a blank value raises `ImproperlyConfigured("The SECRET_KEY environment variable must be set and not empty")`. `settings.py` does `_env = resolve_settings(os.environ, BASE_DIR.parent / ".env")` and assigns from it. No test settings module: the suite loads `config.settings`, so it reads the developer's `.env` (which has `OPENAI_API_KEY`, confirmed by the user).
- **Settings tests** (`config/tests/`): `test_env.py` (`ResolveSettingsTests`, `SimpleTestCase`) calls `resolve_settings` with inline dicts (mostly `{"SECRET_KEY": "x", ...}`), `MISSING_ENV_FILE`, a `write_env_file()` helper; one test per missing/empty/whitespace case with `assertRaisesMessage(ImproperlyConfigured, "SECRET_KEY")`. `test_settings.py` patches `os.environ` with `PATCHED_ENVIRON` (values unlike the defaults) and reloads the settings module, with a cleanup reload; secrets are compared with `assertTrue(a == b)` so a failure never prints them. `test_env_example.py` requires `.env.example` to define exactly `VARIABLES`, each with a `#` line directly above.
- **Docs:** `README.md` Setup has the `.env` steps and a variable table (Variable | Default when unset | Notes); `CLAUDE.md` Stack has the settings bullet and "OpenAI Chat Completions … API key from `.env`".
- **Apps:** `apps.py` is just `class XConfig(AppConfig): name = "x"`; `tests/test_apps.py` asserts `apps.is_installed("x")`. `core` shows an app without models has no `models.py`/`migrations/`. Project apps are listed last in `INSTALLED_APPS` (`…, "resources"`).
- **Tests and style:** `unittest.mock.patch` as context managers; `patch.object` for attributes, string targets for module functions. No logging anywhere yet (no `LOGGING`, no `assertLogs`). Ruff defaults (E4, E7, E9, F; 88 columns). `requirements.txt` range-pins (`Django>=6.1,<6.2`).
- **OpenAI SDK** (checked by installing 3.24.0, the latest, into the venv): `openai.OpenAI(api_key=…, timeout=…, max_retries=…)`, `client.chat.completions.create(model=…, messages=…)`, reply text at `choices[0].message.content`. Every SDK error derives from `openai.OpenAIError` (`APIConnectionError` ⊃ `APITimeoutError`; `APIStatusError` ⊃ `AuthenticationError`, `RateLimitError`, `InternalServerError`). Defaults are `max_retries=2` and a 600-second read timeout, so the 30-second timeout must be set explicitly. Its errors are built from `httpx2` requests/responses (`httpx2` comes with `openai` 3.x; plain `httpx` is not installed — corrected during step 9).

## Design decisions

- **The key is validated like `SECRET_KEY`**, in `resolve_settings`, read raw, with the same message shape ("The OPENAI_API_KEY environment variable must be set and not empty"). Rationale: one pattern for required secrets, and the message never includes the value.
- **Existing env and settings tests get the key first, as a test-only step (step 3)**, before the key becomes required (step 4). Rationale: tdd.md wants test corrections as their own deliberate step, and the suite must stay green after every step.
- **`ai/services.py` has three public names:** `AIServiceError`, `get_client()` (the only place an `openai.OpenAI` is built: key from settings, `TIMEOUT_SECONDS = 30`, `MAX_RETRIES = 2`) and `complete(system, user) -> str`. Rationale: `get_client` is the single patch point the tests replace (AC11), and views in #16/#17 only need `complete` and the error.
- **One user-safe message for all API failures** ("The AI service is unavailable right now. Please try again later.") and one for an empty reply ("The AI service returned an empty reply."), raised `from` the SDK error. Rationale: views can show `str(error)` as is.
- **Log the error type only** (`logger.error("OpenAI request failed: %s", type(error).__name__)` on `logging.getLogger(__name__)`), not the SDK message or traceback. Rationale: the SDK's authentication error echoes part of the key ("Incorrect API key provided: sk-…"), so its text must not reach the logs (AC9).
- **No network in tests:** a small base class in `ai/tests/` patches `ai.services.OpenAI` (the name `services` imports) to fail the test if it is ever called, and service tests patch `get_client` to return a fake that records the request. `get_client`'s own test patches `ai.services.OpenAI` with a mock and checks the arguments, so no real client is built either.
- **`requirements.txt` gets `openai>=3.24,<3.25`**, matching the other range pins; a test reads the file so the pin can't silently disappear.
- **The user's stashed `.env.example` line** (`OPENAI_API_KEY=sk-dummy`) is re-added test-first in step 6 with its comment and `OPENAI_MODEL`; the stash is dropped once the step is committed.

## Steps

- [x] 1. **`ai` app and the `openai` dependency.** `ai` is installed (`apps.is_installed("ai")`), and `requirements.txt` has a range-pinned `openai` line (`openai>=` with an upper bound `<`). — test: `ai/tests/test_apps.py` (new: `AiAppTests`) — impl: `src/ai/__init__.py`, `src/ai/apps.py` (`AiConfig`), `src/ai/tests/__init__.py`, `config/settings.py` (`INSTALLED_APPS`), `requirements.txt` — covers: AC5, AC6 (app)

- [x] 2. **`OPENAI_MODEL` is optional with a default.** `resolve_settings` returns `openai_model`: `gpt-4.1-mini` when unset, empty or whitespace-only; a given value trimmed; the environment beats `.env`. — test: `config/tests/test_env.py` — impl: `config/env.py` (`EnvSettings.openai_model`, `DEFAULT_OPENAI_MODEL`) — covers: AC2, AC3

- [x] 3. **Test-only: the env and settings tests supply a key.** Before the key becomes required, every `resolve_settings` call in `test_env.py` passes an `OPENAI_API_KEY` (through a small `environ(**values)` helper with a dummy key), and `PATCHED_ENVIRON` in `test_settings.py` gets one, unlike `.env.example`'s value. No behaviour change, suite stays green; committed as `test(ai-client): …`. (Precondition, already met: the local `.env` has `OPENAI_API_KEY`.) — test: `config/tests/test_env.py`, `config/tests/test_settings.py` — impl: none — covers: groundwork for AC1

- [x] 4. **`OPENAI_API_KEY` is required.** `resolve_settings` returns `openai_api_key`. Missing, empty and whitespace-only each raise `ImproperlyConfigured` mentioning `OPENAI_API_KEY`, and the message doesn't contain the given value (checked with a whitespace-padded value and a recognisable one). A value starting with `$` is kept literally; the environment beats `.env`; the given mapping and `os.environ` are untouched. — test: `config/tests/test_env.py` — impl: `config/env.py` — covers: AC1, AC3

- [x] 5. **Settings wiring.** After reloading with `PATCHED_ENVIRON`, `settings.OPENAI_API_KEY` equals the patched key (compared without printing it) and `settings.OPENAI_MODEL` the patched model; with `OPENAI_MODEL` removed it is `gpt-4.1-mini`. `settings.py` contains no `sk-` literal. — test: `config/tests/test_settings.py` — impl: `config/settings.py` — covers: AC3

- [x] 6. **`.env.example` documents both.** `VARIABLES` adds `OPENAI_API_KEY` and `OPENAI_MODEL`; each has a comment line above; the key's value is exactly `sk-dummy` and the model's is `gpt-4.1-mini`. Then `git stash drop` the user's earlier edit (its content is now in the commit). — test: `config/tests/test_env_example.py` — impl: `.env.example` — covers: AC4

- [x] 7. **`get_client()` builds the one client.** With `ai.services.OpenAI` patched to a mock and `override_settings(OPENAI_API_KEY=…)`, `get_client()` returns the mock's instance, constructed once with that key, `timeout=30` and `max_retries=2`. The test base class that fails on any real `OpenAI` construction is added here and used by every service test. — test: `ai/tests/test_services.py` (new: `NoNetworkTestCase` base, `GetClientTests`) — impl: `src/ai/services.py` (`get_client`, `TIMEOUT_SECONDS`, `MAX_RETRIES`) — covers: AC7, AC11

- [x] 8. **`complete()` sends one request and returns the trimmed reply.** With `get_client` patched to a fake recording its calls and `override_settings(OPENAI_MODEL="test-model")`: one `chat.completions.create` call, `model="test-model"`, messages `[{"role": "system", …}, {"role": "user", …}]` in that order with the given texts; the fake's reply `"  Hi there \n"` comes back as `"Hi there"`. — test: `ai/tests/test_services.py` (`CompleteTests`) — impl: `src/ai/services.py` (`complete`) — covers: AC6, AC7, AC11

- [x] 9. **API errors become `AIServiceError`.** For `APIConnectionError`, `APITimeoutError`, `AuthenticationError`, `RateLimitError` and `InternalServerError` raised by the fake (built with `httpx2` requests/responses; the authentication one's message contains a key-like string), `complete()` raises `AIServiceError` with the user-safe message, `__cause__` is the SDK error, and the message contains neither the key nor the SDK text. `assertLogs("ai.services", "ERROR")` sees one record naming the error type, without the key-like string or the SDK message. — test: `ai/tests/test_services.py` (`CompleteErrorTests`) — impl: `src/ai/services.py` (`AIServiceError`, logger, `except OpenAIError`) — covers: AC8, AC9

- [ ] 10. **An empty reply is an error too.** No choices, `content=None`, and whitespace-only content each raise `AIServiceError` with the empty-reply message (logged like step 9). — test: `ai/tests/test_services.py` (`CompleteEmptyReplyTests`) — impl: `src/ai/services.py` — covers: AC10

- [ ] 11. **Docs.** `CLAUDE.md`: Stack (the settings bullet: `OPENAI_API_KEY` required like `SECRET_KEY`, a dummy is enough for tests and the dev server; `OPENAI_MODEL` default; the OpenAI bullet: `ai.services.complete`, `AIServiceError`, `get_client` as the patch point, 30 s / 2 retries, no network in tests), Commands (the `cp .env.example .env` comment), Layout (`src/ai/`). `README.md`: the Setup steps and the variable table get both variables, and the note that the suite needs the key. No test (docs only). — test: none — impl: `CLAUDE.md`, `README.md` — covers: AC12

## AC coverage

| AC | Steps |
|----|-------|
| AC1 key required, not in message, literal | 3, 4 |
| AC2 model optional, default, trimmed | 2 |
| AC3 env beats `.env`, settings wiring, nothing hardcoded | 2, 4, 5 |
| AC4 `.env.example` | 6 |
| AC5 `openai` pinned | 1 |
| AC6 `ai` app, `complete()` | 1, 8 |
| AC7 one request, model, messages, key, timeout, retries | 7, 8 |
| AC8 `AIServiceError`, safe message, chained | 9 |
| AC9 logged without the key | 9 |
| AC10 empty reply | 10 |
| AC11 no network | 7, 8 |
| AC12 docs | 11 |
