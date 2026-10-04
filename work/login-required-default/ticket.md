# Auth: secure-by-default login with LoginRequiredMiddleware
Issue: #42 · Branch: feature/login-required-default

## Story
As the maintainer of Learning Companion, I want every page to require a logged-in user unless it is explicitly marked public, so that a view whose author forgets `LoginRequiredMixin` fails closed instead of leaking data to anonymous visitors.

## Acceptance criteria
- [ ] AC1 `django.contrib.auth.middleware.LoginRequiredMiddleware` is in `MIDDLEWARE` after `AuthenticationMiddleware`, while `WhiteNoiseMiddleware` stays second and `AxesMiddleware` stays last (the existing order pins keep passing).
- [ ] AC2 A view with no login protection of its own (a test-only URLconf with a plain function view, no mixin or decorator) redirects an anonymous GET to `/accounts/login/?next=<path>` and renders for a logged-in user.
- [ ] AC3 Home (`/`) stays public: an anonymous GET is 200 with the same content as today. `core.views.home` is marked `@login_not_required`.
- [ ] AC4 The favicon (`/favicon.ico`) stays public: an anonymous GET and HEAD return the icon (200, same headers as today). `core.views.favicon` is marked `@login_not_required`, so the Docker HEALTHCHECK keeps working.
- [ ] AC5 Sign-up (`/accounts/signup/`) stays public: an anonymous GET is 200 and an anonymous POST with valid data creates the user, logs them in and lands on `/dashboard/`. A logged-in visit still redirects to `/dashboard/`. `SignUpView` is marked `login_not_required`.
- [ ] AC6 Log-in (`/accounts/login/`) stays public: an anonymous GET is 200 and a valid POST logs in (exempt through Django's own `LoginView`, pinned by a test, not by a new decorator).
- [ ] AC7 Log-out stays public: an anonymous POST to `/accounts/logout/` still redirects to `/` with no "You have been logged out." message (the existing test keeps passing). `LogOutView` is marked `login_not_required`. GET is still 405.
- [ ] AC8 The django-axes lockout page still renders for anonymous visitors: a locked-out POST to `/accounts/login/` and to `/admin/login/` is 429 with the lockout text (existing lockout tests keep passing).
- [ ] AC9 Admin: an anonymous GET to `/admin/` redirects to `/accounts/login/?next=/admin/` (the app's log-in, accepted behaviour, pinned by a test). `/admin/login/` stays reachable anonymously (200).
- [ ] AC10 Fail-closed route walker: a test resolves every URL pattern in the root URLconf (including `include()`d ones, with sample kwargs for path converters) and asserts that each view outside an explicit public allow-list (home, favicon, sign-up, log-in, log-out, admin login) is not marked `login_not_required`, and that an anonymous GET to it redirects to the log-in URL (admin routes: to the app or admin log-in). The allow-list's views are each marked public. A route that is in neither the walker's known set nor the allow-list fails the test, so a new public route has to be added deliberately.
- [ ] AC11 The existing `LoginRequiredMixin`s on private views are kept (defence in depth), and every existing anonymous-redirect test keeps passing unchanged.
- [ ] AC12 `CLAUDE.md` (Auth section, the favicon note, layout) and `README.md` where it applies describe the middleware, the public views and the rule "a new public view needs `@login_not_required` and an allow-list entry in the walker test".

## Out of scope
- Removing `LoginRequiredMixin` from existing views.
- Keeping admin's own redirect to `/admin/login/` (no custom `AdminSite`).
- Custom 404/500 pages; unknown paths stay 404 for anonymous visitors (the middleware only acts on resolved URLs).
- Any change to log-in, sign-up or log-out behaviour beyond staying public.

## Notes
Answered in the interview (2026-10-04):
- Mixins: keep them alongside the middleware.
- Log-out: stays public (`@login_not_required`), so an expired-session tab can still log out cleanly.
- Admin: accept the redirect to the app's log-in for anonymous `/admin/`; `AdminSite.login` is already `login_not_required` in Django.
- Guard test: walk every route against an explicit public allow-list.

Constraints from the codebase:
- Django 6.1: `LoginView.dispatch` already carries `login_not_required`; `LogoutView` does not. `SignUpView` already uses `@method_decorator(sensitive_post_parameters(...), name="dispatch")`.
- `MIDDLEWARE[:2]` (WhiteNoise second) is pinned in `config/tests/test_settings.py`, `MIDDLEWARE[-1]` (Axes last) in `accounts/tests/test_lockout.py`.
- The Docker HEALTHCHECK and `scripts/docker-smoke.sh` request `/favicon.ico`, `/`, sign-up and log-in anonymously; `/no-such-page/` must stay 404.
- `GoalSessionsMixin`/`GoalResourcesMixin` check `request.user.is_authenticated` in `dispatch`; that stays harmless.
- `core/tests/pages.py` lists the public pages (home, log in, sign up, locked out); the walker's allow-list must agree with it.

Acceptance criteria approved by the user on 2026-10-04.
