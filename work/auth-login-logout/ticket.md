# Auth: log in and log out
Issue: #4 · Branch: feature/auth-login-logout

## Story
As a registered user of the Learning Companion, I want to log in and out, and get back to the page I was trying to open, so that I can use my account safely across visits.

## Acceptance criteria
- [ ] AC1 Login and logout URLs exist in the `accounts` namespace:
  - `reverse("accounts:login")` is `/accounts/login/` and `reverse("accounts:logout")` is `/accounts/logout/`
  - `settings.LOGIN_URL` resolves to `/accounts/login/`
  - `settings.LOGOUT_REDIRECT_URL` is `"/"`
  - Only these two views are added, not the whole `django.contrib.auth.urls`, so no password-reset or password-change routes exist.
- [ ] AC2 An anonymous `GET /accounts/login/` returns 200 and renders `accounts/login.html`, which extends `base.html`. The page contains a `method="post"` form whose `action` is `reverse("accounts:login")`, with the fields `username` and `password` and a CSRF token.
- [ ] AC3 A valid `POST` with no `next` logs the user in (the session's authenticated user is that user) and redirects to `settings.LOGIN_REDIRECT_URL`.
- [ ] AC4 After a successful login, the page the user lands on shows "Welcome back, <username>!".
- [ ] AC5 A failed login re-renders the form with status 200. The page shows Django's error "Please enter a correct username and password. Note that both fields may be case-sensitive.". No one is logged in, and the submitted password does not appear in the response. The case for a wrong password and the case for an unknown username show exactly the same message, so the page doesn't reveal which usernames exist.
- [ ] AC6 A safe `next` is honoured. When the login page is opened with `?next=/some/page/?a=1` (a path on this site), the form carries `next`, and a valid `POST` with it redirects to `/some/page/?a=1`.
- [ ] AC7 An unsafe `next` is never followed. A valid `POST` with any of the following as `next` still logs the user in, but redirects to `settings.LOGIN_REDIRECT_URL`, and the `Location` header never points off-site:
  - an absolute external URL: `https://evil.example/`
  - a scheme-relative URL: `//evil.example/`
  - a backslash variant browsers treat as external: `/\evil.example/` and `\\evil.example`
  - a non-HTTP scheme: `javascript:alert(1)`
  - a look-alike host: `https://testserver.evil.example/`
  - the same cases passed in the query string (`GET ?next=`) and then posted
- [ ] AC8 For a logged-in user, `GET` and `POST` to `/accounts/login/` redirect to `settings.LOGIN_REDIRECT_URL`. The form is not shown.
- [ ] AC9 Logout works only by `POST`. A `POST /accounts/logout/` by a logged-in user ends the session (the user is anonymous afterwards) and redirects to `settings.LOGOUT_REDIRECT_URL`, where the page shows "You have been logged out.". A `GET /accounts/logout/` returns 405 and leaves the user logged in.
- [ ] AC10 The nav reflects the auth state:
  - anonymous: exactly "Goals Log in Sign up", where "Log in" links to `reverse("accounts:login")`, "Sign up" links to `reverse("accounts:signup")`, and "Goals" stays a non-link placeholder
  - logged in: "Goals", the username, and a "Log out" button inside a `method="post"` form whose `action` is `reverse("accounts:logout")` and which carries a CSRF token. There are no "Log in" or "Sign up" links.
- [ ] AC11 The full round trip works in one test client session: sign up or create a user, log out (POST), confirm anonymous, log back in with the same password, and confirm logged in.
- [ ] AC12 CSRF is enforced on login and logout. With a CSRF-enforcing client (`Client(enforce_csrf_checks=True)`):
  - a login `POST` without a CSRF token returns 403 and logs no one in
  - a logout `POST` without a token returns 403 and leaves the user logged in
  - a logout `POST` with the token taken from the nav's logout form succeeds, which proves the nav button carries a working token
- [ ] AC13 The session is replaced at login and invalidated at logout:
  - after a successful login, the session key differs from the anonymous session key the visitor had before (session-fixation protection)
  - after logout, a request that reuses the old session cookie is anonymous
- [ ] AC14 A deactivated account can't log in. A user with `is_active=False` who submits the correct password gets the same generic error as in AC5 (not a separate "inactive" message) and is not logged in.
- [ ] AC15 A malicious `next` can't inject markup into the login page. `GET /accounts/login/?next="><script>alert(1)</script>` returns a page that doesn't contain the raw string `<script>alert(1)</script>`; the value appears only escaped (reflected-XSS protection).

## Out of scope
- Password reset and password change flows (and their routes).
- A `next` field on the logout form. The nav's logout form sends no `next`, so logging out from the UI always lands on `LOGOUT_REDIRECT_URL`. Django's `LogoutView` still honours a `next` that is posted directly, validated with the same `url_has_allowed_host_and_scheme` check as login. That is Django's native behaviour, which the user chose to keep (plan review, 2026-10-02).
- Cross-links between the login and sign-up pages (the user chose not to add them).
- Pages that require login (`login_required`). The Goals tickets add them. This ticket only makes `next` work and safe for them.
- Rate limiting and lockout of repeated failed logins (deployment hardening, like #3's deferred findings).
- "Remember me" or session-length options.

## Notes
Answers from refinement (2026-10-02):
- **`next` after login: honoured, safe URLs only (option 1).** The user wanted it to be impossible for scammers to misuse it.
  - `next` only picks the redirect target after a successful login. It never grants access: the target page still applies its own login and ownership checks, so a `next` pointing at someone else's data just lands on a page that refuses access.
  - The real threat is an **open redirect**, where a genuine login link sends the victim to a phishing site. AC7 pins Django's `url_has_allowed_host_and_scheme` check against the common bypass tricks (absolute, scheme-relative, backslash, non-HTTP scheme, look-alike host), for both `GET` and `POST` `next`.
- After logout: redirect to `/` (`LOGOUT_REDIRECT_URL`) and show "You have been logged out.".
- A logged-in user opening the login page is redirected to `LOGIN_REDIRECT_URL`, consistent with sign-up (#3 AC8).
- Extras: a "Welcome back, <username>!" message after login. No cross-links.
- Failed logins use one generic message for both an unknown username and a wrong password, so the login page doesn't reveal which usernames exist. Sign-up still reveals taken usernames, which #3 accepted as inherent.
- Security review of the draft (2026-10-02, approved by the user): AC12–AC15 were added to pin protections Django already provides, so a later refactor can't silently drop them:
  - CSRF enforced on login and logout. Logout CSRF would let any site log users out.
  - Session key rotation at login, and invalidation at logout.
  - Deactivated accounts can't log in and aren't revealed. Django's default `ModelBackend` rejects `is_active=False`, so `AuthenticationForm` raises its generic `invalid_login` error. The separate "This account is inactive." message only appears with `AllowAllUsersModelBackend`, which this project doesn't use.
  - Escaped output of `next` in the login form's hidden field.
- **Usernames are case-sensitive at login** (Django's default): `Alice` doesn't log in as `alice`. This is a usability point, not a security one, because sign-up (#3 AC7) already rejects usernames that differ only in case. Keep the default.

Constraints and context:
- #3 set `LOGIN_REDIRECT_URL = "/"` and created the `accounts` app with the namespace `accounts`. The login view reuses both.
- Logout must be a `POST`: Django 5+ `LogoutView` rejects `GET` with 405. The nav button is a small form with `{% csrf_token %}`.
- **This ticket deliberately changes earlier ACs.** #2's AC4 ("Log in" is a non-link placeholder) and #3's AC9 (the anonymous nav "Goals · Log in · Sign up" with only the Sign up link) assumed "Log in" stays a placeholder until this ticket. Their tests are updated deliberately in their own step (`.claude/rules/tdd.md`: fix a test deliberately, never weaken it). "Goals" stays a non-link placeholder.
- The login template is `src/templates/accounts/login.html`, extending `base.html`, following the #2 and #3 convention.
- `CLAUDE.md` and `README.md` get the login and logout URLs and the redirect settings. The plan includes this.

Status: the user approved these acceptance criteria (AC1–AC15) on 2026-10-02. The next step is `plan-ticket`.
