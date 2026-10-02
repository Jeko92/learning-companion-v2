# Auth: sign up
Issue: #3 · Branch: feature/auth-signup

## Story
As a visitor to the Learning Companion, I want to create an account with a username and password and be logged in straight away, so that I can start tracking my learning without a separate log-in step.

## Acceptance criteria
- [ ] AC1 A new `accounts` app is in `INSTALLED_APPS`. Its URLs are included under `/accounts/`, and `reverse("accounts:signup")` is `/accounts/signup/`.
- [ ] AC2 An anonymous `GET /accounts/signup/` returns 200 and renders `accounts/signup.html`, which extends `base.html`. The page contains a form with the fields `username`, `password1` and `password2`, plus a CSRF token (`csrfmiddlewaretoken`).
- [ ] AC3 A valid `POST` creates exactly one user with the submitted username. The password is stored hashed: `check_password` succeeds, and the raw password is not stored.
- [ ] AC4 After a valid `POST`, the new user is logged in (the session's authenticated user is the new user) and the response redirects to `/`.
- [ ] AC5 Following that redirect, the home page shows the message "Welcome, <username>!".
- [ ] AC6 An invalid `POST` re-renders the form with status 200, shows the field errors, creates no user and logs no one in. It is checked for:
  - mismatched passwords
  - a username that already exists
  - a password rejected by the configured password validators (e.g. too short or too common)
- [ ] AC7 For a logged-in user, both `GET` and `POST` to `/accounts/signup/` redirect to `/`. The form is not rendered and no user is created.
- [ ] AC8 For anonymous visitors, the nav shows a "Sign up" link to `/accounts/signup/`. For logged-in users there is no such link. "Goals" and "Log in" stay non-link placeholders.
- [ ] AC9 For a logged-in user, the nav shows their username, which signals that they are signed in. Anonymous visitors see no username in the nav.

## Out of scope
- Email at sign-up, email verification, password reset, social login.
- Log in and log out pages and real "Log in" and "Log out" links (ticket `auth-login-logout`, #4).
- Profile fields and a profile page (profile tickets). After sign-up the user goes to `/`, not to a profile page.
- Making the username in the nav a link (there is no profile page yet).

## Notes
Answers from refinement (2026-10-02):
- Fields: username and password only, using Django's `UserCreationForm` as is (username, password, confirmation). No email.
- After sign-up: log the user in, redirect to `/`, and add a success message "Welcome, <username>!". The base layout already renders messages (#2, AC5).
- A logged-in user opening the sign-up page (`GET` or `POST`) is redirected to `/`, with no message.
- Nav for a logged-in user: show their username as plain text, so it's clear they are signed in (added at the user's request after the first draft). Don't show the "Sign up" link.
- Location: a new `accounts` app with the URL namespace `accounts`, mounted at `/accounts/`. Ticket #4 adds Django's log-in and log-out views under the same prefix.

Constraints and context:
- Following #2, project-wide templates live in `src/templates/`, so the page template is `src/templates/accounts/signup.html`. It extends `base.html`.
- Django's default `AUTH_PASSWORD_VALIDATORS` (similarity, minimum length, common, numeric) are already configured. AC6's validator case relies on them.
- #2's nav test asserts that "Goals" and "Log in" are not inside any link. Adding a real "Sign up" link must keep that test green.
- `CLAUDE.md` and `README.md` get the `accounts` app in their Layout sections. The plan includes this.
