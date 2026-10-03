# AI: OpenAI client service and API key config
Issue: #15 · Branch: feature/ai-client

## Story
As the developer of the learning companion, I want one small, tested service that sends a prompt to the OpenAI Chat Completions API using a key and model from the environment, so that the summary (#16) and next-steps (#17) features can call the AI without dealing with keys, timeouts or API errors themselves.

## Acceptance criteria

**Configuration (`config/env.py`, `settings.py`)**
- [x] AC1 `OPENAI_API_KEY` is required, like `SECRET_KEY`. If it is missing, empty or whitespace-only, settings fail to load with `ImproperlyConfigured` naming the variable. The value is read literally (a `$` is not expanded) and never appears in the error message.
- [x] AC2 `OPENAI_MODEL` is optional and defaults to `gpt-4.1-mini`. The value is trimmed, and an empty or whitespace-only value means the default.
- [x] AC3 Both are read through `resolve_settings()`: the process environment beats `.env`, and the given environment is never modified. `settings.OPENAI_API_KEY` and `settings.OPENAI_MODEL` come from the environment, and no key is hardcoded in `settings.py`.
- [x] AC4 `.env.example` documents `OPENAI_API_KEY` (with the placeholder `sk-dummy`, never a real key) and `OPENAI_MODEL`, each with a comment line above it, and `test_env_example.py` lists them.
- [x] AC5 The `openai` SDK is in `requirements.txt`, range-pinned like the other dependencies.

**Service (`ai` app)**
- [x] AC6 A new `ai` app is installed. `ai.services` has one public function that takes a system prompt and a user message and returns the reply text, trimmed.
- [x] AC7 The function sends one Chat Completions request: the model from `settings.OPENAI_MODEL` and the messages `[system, user]` in that order. The client is built with `settings.OPENAI_API_KEY`, a 30-second timeout and 2 retries (the SDK retries connection errors, 429 and 5xx with backoff).
- [x] AC8 Any OpenAI SDK error (connection error, timeout, authentication, rate limit, server error) is raised as one project exception, `ai.services.AIServiceError`. Its message is safe to show a user and contains neither the key nor the raw API error. The original error is chained (`__cause__`).
- [x] AC9 Each failure is logged at error level on a module logger with the error type, never with the key.
- [x] AC10 A reply without content (no choices, `None` or blank text) is also an `AIServiceError`.
- [x] AC11 No test makes a network call. The client is created in one place that the tests replace with a fake, and the service tests fail loudly if a real `openai.OpenAI` client would be constructed.

**Docs**
- [x] AC12 `CLAUDE.md` (Stack, Layout, the settings bullet) and `README.md` (setup) document the `ai` app, the service function and its error, `OPENAI_API_KEY` (required, a dummy value is enough for tests and the dev server) and `OPENAI_MODEL`.

## Out of scope
- The summary (#16) and next-steps (#17) features: their prompts, views and templates
- Streaming, caching, cost tracking, per-user rate limiting
- Configuring timeout or retries through the environment
- Any other AI provider

## Notes
- **Model:** the user chose `gpt-4.1-mini` as the default, overridable through `OPENAI_MODEL`. No `temperature` or other sampling parameters are set in this ticket.
- **Missing key:** the user chose *required at startup* (like `SECRET_KEY`) over an optional key that fails only when used. Consequence: every environment that loads settings needs a value, including the test suite, the dev server and the planned Docker and CI tickets (#20, #21). The tests never call the API, so any non-empty dummy value works there.
- **Local `.env`:** the hooks run the suite with the real `.env`. Before the step that makes the key required, the developer's `.env` needs an `OPENAI_API_KEY` line (a dummy is fine), or every hook run goes red. The plan must order this explicitly.
- **Timeout and retries:** 30 seconds and the SDK's 2 retries, fixed in code.
- **Location:** a new `ai` app (`src/ai/`), per the one-app-per-domain layout; #16 and #17 build on its service.
- **Error path:** callers catch only `AIServiceError`; it hides the SDK's exception types from the views.
- The issue's open questions (default model and env configuration, timeout and retries) were answered in the interview on 2026-10-03.
- **Approval:** the user approved the acceptance criteria (AC1–AC12) on 2026-10-03, keeping the key required at startup.
- **Placeholder:** after approval the user asked for `sk-dummy` as the `.env.example` key placeholder (AC4 updated). Their uncommitted `.env.example` edit was stashed (`git stash list`) because it turned `test_env_example` red and blocked commits; the AC4 step re-adds it test-first. The real key is in the local `.env`.
