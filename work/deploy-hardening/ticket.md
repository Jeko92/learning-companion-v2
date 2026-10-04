# DevOps: deployment hardening (failed-login lockout, secure cookies, HSTS and SSL redirect via environment settings, clean `check --deploy`)
Issue: #36 · Branch: feature/deploy-hardening

## Story
As the operator of Learning Companion, I want the production configuration to be secure by default: repeated failed log-ins locked out, cookies sent only over HTTPS, HTTPS enforced, and `manage.py check --deploy` clean. That way a plain `DEBUG=False` deployment isn't open to password guessing or cookie theft, and I can still loosen single settings through the environment when a setup needs it (a local HTTP smoke run, a TLS-terminating proxy).

## Acceptance criteria

### Failed-login lockout (django-axes)
- [ ] AC1 `django-axes` is a pinned requirement (`django-axes>=8.3,<8.4` in `requirements.txt`, pinned by the requirements test) and is installed as an app with its middleware and authentication backend. The backend comes first, then Django's `ModelBackend`, so normal log-in keeps working.
- [ ] AC2 After 5 failed log-ins for the same username from the same IP address within 15 minutes, the 6th attempt for that username and IP is refused, even with the correct password. Nobody is logged in and no session is created.
- [ ] AC3 A lockout is per username + IP. The same username from another IP can still log in, and so can another username from the same IP.
- [ ] AC4 A refused attempt gets HTTP 429 and a page that extends `base.html`. It has the title `Locked out · Learning Companion` and one `<h1>`, and it says, without naming the account or confirming that it exists: "Too many failed log-in attempts. Try again in 15 minutes." Its markup follows the site-wide conventions, because it is added to `core/tests/pages.py` as a new page type.
- [ ] AC5 A non-existent username is counted and locked out exactly like an existing one, so the lockout doesn't reveal whether an account exists.
- [ ] AC6 The lockout lifts once 15 minutes have passed since the last failure: the correct password logs in again.
- [ ] AC7 A successful log-in before the limit resets that username + IP's failure count.
- [ ] AC8 The admin log-in (`/admin/login/`) is covered by the same lockout.
- [ ] AC9 The limit (5), the cool-off (15 minutes) and the lockout parameters (username + IP) are set in `settings.py`, and a test pins each value. Failures are stored in the database through axes' models, so every gunicorn worker sees the same counts.

### HTTPS settings from the environment
- [ ] AC10 With `DEBUG=False` and no override, the following are on: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` and `SECURE_HSTS_SECONDS` (a positive default, documented). With `DEBUG=True` and no override, all of them are off (HSTS `0`).
- [ ] AC11 Each of the four can be set explicitly through an env var of the same name: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` and `CSRF_COOKIE_SECURE` are booleans, `SECURE_HSTS_SECONDS` is a non-negative integer. An explicit value beats the DEBUG-derived default in both directions, and a blank value means the default. An invalid value (`SECURE_HSTS_SECONDS=abc` or `-1`) is an `ImproperlyConfigured` that names the variable.
- [ ] AC12 `SECURE_PROXY_SSL_HEADER` is opt-in. When the env var `SECURE_PROXY_SSL_HEADER` is true, it is `("HTTP_X_FORWARDED_PROTO", "https")`, otherwise unset (`None`), in both DEBUG modes.
- [ ] AC13 With the SSL redirect on, a plain-HTTP request for a page gets a 301 to the `https://` URL. `/favicon.ico` is exempt, so the container's HTTP `HEALTHCHECK` keeps working with the default settings.
- [ ] AC14 With HSTS on, an HTTPS response carries `Strict-Transport-Security: max-age=<seconds>`, without `includeSubDomains` or `preload`.
- [ ] AC15 Every new variable is documented in `.env.example`, as a commented-out example (added to `COMMENTED_EXAMPLES`, because a blank `--env-file` line would override the default), and in the README's variable table. Each is also in `test_settings.py`'s `PATCHED_ENVIRON` with a non-default value, so a developer's `.env` can't leak into the tests.
- [ ] AC16 The test suite passes whatever `DEBUG` is in the environment, including CI, which doesn't set `DEBUG` at all.

### Email
- [ ] AC17 With `DEBUG=True`, mail goes to the console backend. With `DEBUG=False`, it goes to Django's default SMTP backend. No new env vars.

### `check --deploy`
- [ ] AC18 `manage.py check --deploy --fail-level WARNING` exits 0 under these settings: `DEBUG=False`, a 50+ character dummy `SECRET_KEY` and no HTTPS overrides. `security.W005` (HSTS includeSubDomains) and `security.W021` (HSTS preload) are the only silenced checks, each with a comment explaining why. A test runs the check.
- [ ] AC19 CI's `quality` job runs that check as its own named step, with the step's own env (`DEBUG=False` and a long dummy key). The step references no secrets, and `test_ci.py` pins it.

### Container and smoke script
- [ ] AC20 `scripts/docker-smoke.sh` still passes end to end. Its HTTP form and page checks turn the HTTPS settings off through `-e` overrides. It also checks a container with the default settings:
  - `/favicon.ico` is served over HTTP (healthy),
  - `/` redirects (301) to `https://`,
  - the HTTP response carries no `Strict-Transport-Security` header, because Django sends it only over HTTPS.
- [ ] AC21 The README (Run with Docker, the env table) and `CLAUDE.md` describe the following:
  - the lockout and how to clear it (`axes_reset`),
  - the HTTPS defaults and their overrides,
  - the proxy header,
  - the email backend switch,
  - the CI step.

## Out of scope
- Per-user rate limits or quotas on the AI summary and next-steps actions. `work/ai-summary/ticket.md` pointed them here, but they are a separate concern and go to a follow-up backlog item.
- The client IP behind a reverse proxy (`X-Forwarded-For`, django-ipware, `AXES_IPWARE_PROXY_COUNT`). Without it, axes uses `REMOTE_ADDR`, so behind a proxy every client shares the proxy's IP and the lockout is effectively per username. The README documents this limitation.
- HSTS `includeSubDomains` and `preload`. They commit the whole domain, so they stay off and their checks are silenced with a reason.
- A real outgoing-mail configuration (SMTP host and credentials through env). The app sends no email yet.
- Throttling sign-up, password reset (no such feature) and other endpoints.
- Applying branch protection or any GitHub settings.

## Notes
- **Decisions (user, interview 2026-10-04):**
  - Lockout through django-axes, not an in-house throttle.
  - Policy: username + IP, 5 failures, 15-minute cool-off.
  - HTTPS settings are on when `DEBUG=False`, with per-setting env overrides; the proxy header is opt-in.
  - Console email only when `DEBUG`, the default SMTP backend otherwise.
- **Compatibility risk:** django-axes 8.3.1 (latest) lists Django 4.2/5.2/6.0 and Python up to 3.14, and requires only `django>=4.2`; Django 6.1 isn't listed. The suite (log-in, admin, `check`, migrations) has to prove that it works. If it doesn't, stop and report; don't patch around it.
- **axes requires the request** in `authenticate()`. Existing tests that log in through `client.login()` or call `authenticate()` without a request may need `force_login` or a request. Fixing those tests is part of this ticket, but never by weakening an assertion.
- **Today's state** (`check --deploy` on develop, `DEBUG=False`): `mail.E001` (console email backend) and W004, W008, W009, W012 and W016. W009 is only the dummy key.
- **Docker constraint:** the `HEALTHCHECK` (`urllib` to `http://127.0.0.1:8000/favicon.ico`) and the smoke script talk plain HTTP. An SSL redirect would make `urlopen` follow to `https://` and fail, and Secure cookies aren't sent by curl over `http://`. Hence AC13 and AC20.
- **Earlier deferrals this ticket closes:**
  - `work/auth-login-logout/` (log-in throttling)
  - `work/auth-signup/review.md` (cookie and HSTS settings from env, `check --deploy`, admin throttling)
  - `work/docker/ticket.md` (secure cookies, HSTS, SSL redirect, proxy header, clean `check --deploy`)
