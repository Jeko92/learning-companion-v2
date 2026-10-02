# Auth: sign up
Issue: #3 · Branch: feature/auth-signup

## Story
As a visitor to the Learning Companion, I want to create an account with a username and password and be logged in straight away, so that I can start tracking my learning without a separate log-in step.

## Acceptance criteria
- [ ] AC1 A new `accounts` app is in `INSTALLED_APPS`. Its URLs are included under `/accounts/` with the namespace `accounts`, and `reverse("accounts:signup")` is `/accounts/signup/`.
- [ ] AC2 The project uses a custom user model:
  - `settings.AUTH_USER_MODEL == "accounts.User"`
  - `get_user_model()` is `accounts.models.User`, a subclass of `AbstractUser` that adds no fields
  - it is registered in the admin with `django.contrib.auth.admin.UserAdmin` (or a subclass of it)
- [ ] AC3 An anonymous `GET /accounts/signup/` returns 200 and renders `accounts/signup.html`, which extends `base.html`. The page contains a `method="post"` form whose `action` is `reverse("accounts:signup")`. The form has the fields `username`, `password1` and `password2`, plus a CSRF token (`csrfmiddlewaretoken`).
- [ ] AC4 A valid `POST` creates exactly one `accounts.User` with the submitted username. The password is stored hashed: `check_password` succeeds, and the raw password is not stored.
- [ ] AC5 After a valid `POST`, the new user is logged in (the session's authenticated user is the new user), and the response redirects to `settings.LOGIN_REDIRECT_URL`, which is set to `"/"`.
- [ ] AC6 Following that redirect, the home page shows the message "Welcome, <username>!".
- [ ] AC7 An invalid `POST` re-renders the form with status 200. It creates no user, logs no one in, and doesn't echo the submitted passwords: neither submitted password value appears in the response. Each error is attached to the field it belongs to, which `assertFormError` can check:
  - mismatched passwords: error on `password2`
  - a username that already exists with the same spelling: error on `username`
  - a username that differs from an existing one only in case (e.g. `Alice` when `alice` exists): error on `username`
  - a password rejected by the configured password validators (e.g. too short or too common): error on `password2`
- [ ] AC8 For a logged-in user, both `GET` and `POST` to `/accounts/signup/` redirect to `settings.LOGIN_REDIRECT_URL`. The form is not rendered and no user is created.
- [ ] AC9 For anonymous visitors, the nav shows "Goals" and "Log in" as non-link placeholders and a "Sign up" link to `reverse("accounts:signup")`. For logged-in users, the nav shows "Goals" (still a non-link placeholder) and neither "Log in" nor the "Sign up" link.
- [ ] AC10 For a logged-in user, the nav shows their username (`user.get_username()`), which signals that they are signed in. Anonymous visitors see no username in the nav.

## Out of scope
- Email at sign-up, email verification, password reset, social login.
- Log in and log out pages and real "Log in" and "Log out" links (ticket `auth-login-logout`, #4). Until #4 lands, a new user cannot log out from the UI.
- A `?next=` redirect parameter after sign-up. It needs `url_has_allowed_host_and_scheme` validation to be safe, so it should be designed deliberately with #4's login view.
- Rate limiting and brute-force protection for sign-up (deployment hardening).
- Extra fields on the user model. Profile data goes into the `Profile` model (profile tickets), not onto `User`.
- Profile fields and a profile page (profile tickets). After sign-up the user goes to `LOGIN_REDIRECT_URL`, not to a profile page.
- Making the username in the nav a link (there is no profile page yet).

## Notes
Answers from refinement (2026-10-02):
- Fields: username and password only (username, password, confirmation). The form is a thin subclass of Django's `UserCreationForm` whose `Meta.model` is the custom `accounts.User`, because `UserCreationForm` is bound to `auth.User`. No email.
- After sign-up: log the user in, redirect to `LOGIN_REDIRECT_URL` (`"/"`), and add a success message "Welcome, <username>!". The base layout already renders messages (#2, AC5).
- A logged-in user opening the sign-up page (`GET` or `POST`) is redirected to `LOGIN_REDIRECT_URL`, with no message.
- Nav for a logged-in user: show their username as plain text (`user.get_username()`, autoescaped), so it's clear they are signed in. This was added at the user's request after the first draft. Don't show the "Sign up" link.
- Location: a new `accounts` app with the URL namespace `accounts`, mounted at `/accounts/`. Ticket #4 adds Django's log-in and log-out views under the same prefix and reuses `LOGIN_REDIRECT_URL`.
- Best-practice review: after the first draft the user approved four changes (2026-10-02):
  1. a custom user model from the start
  2. `LOGIN_REDIRECT_URL` and `reverse()` instead of hardcoded URLs
  3. the case-insensitive duplicate username case
  4. explicit scope edges (`?next=`, rate limiting)
- Second review, also approved (2026-10-02): AC7 now also checks that submitted passwords are not echoed back, and that each error sits on its field. Django 6.1's `SetPasswordMixin` puts both the mismatch and the validator errors on `password2`. `clean_username` puts duplicate errors on `username`.

Constraints and context:
- **Custom user model now, before any model references the user.** Django recommends setting `AUTH_USER_MODEL` at the start of a project. Changing it later, once other models point at the user, needs a hand-written data migration.
  - Code must refer to the user model only through `get_user_model()` or `settings.AUTH_USER_MODEL`, never `django.contrib.auth.models.User`.
  - `accounts/migrations/0001_initial.py` creates the user table.
- **One-time local database reset.** The local `src/db.sqlite3` already has the built-in `auth` tables migrated. After the swap, `migrate` would fail with `InconsistentMigrationHistory`. So the plan includes a manual step: delete `src/db.sqlite3` and run `migrate` again. It holds no data worth keeping. The test database is created fresh on every run, so tests are unaffected.
- Following #2, project-wide templates live in `src/templates/`, so the page template is `src/templates/accounts/signup.html`. It extends `base.html`.
- Django's default `AUTH_PASSWORD_VALIDATORS` (similarity, minimum length, common, numeric) are already configured. AC7's validator case relies on them. Django 6.1's `UserCreationForm` rejects usernames that match an existing one case-insensitively, and AC7 pins that behaviour.
- #2's nav test asserts that "Goals" and "Log in" are not inside any link. Adding a real "Sign up" link must keep that test green.
- `CLAUDE.md` and `README.md` get the `accounts` app and the custom user model (`AUTH_USER_MODEL`) in their Layout and Stack sections. The plan includes this.
- Plan review (2026-10-02, approved): the plan's first draft would have shown the "Log in" placeholder to logged-in users, next to their username. AC9 now hides "Log in" from logged-in users, so the nav is "Goals · Log in · Sign up" when anonymous and "Goals · <username>" when logged in. #4 adds "Log out" to the logged-in nav.

Status: the user approved these acceptance criteria (AC1–AC10) on 2026-10-02. The next step is `plan-ticket`.
