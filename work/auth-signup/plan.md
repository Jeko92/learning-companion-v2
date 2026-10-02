# Plan: auth-signup

## Research summary
- **Project:**
  - `INSTALLED_APPS` is the 6 contrib apps, then `django_tailwind_cli` and `core`. There is no `AUTH_USER_MODEL`, `LOGIN_REDIRECT_URL` or `LOGIN_URL` yet.
  - The 4 default `AUTH_PASSWORD_VALIDATORS` are configured. `MinimumLengthValidator` uses its default of 8.
  - Middleware: `SessionMiddleware`, `CsrfViewMiddleware`, `AuthenticationMiddleware`, `MessageMiddleware`.
  - The `request`, `auth` and `messages` context processors are active, so `user` is available in every template.
  - `config/urls.py`: `admin/`, plus `include("core.urls")` at `""`. `core.urls` has no `app_name`.
  - No code imports `django.contrib.auth.models.User`, and no app has a `migrations/` package yet.
- **Local DB:** `src/db.sqlite3` (git-ignored) has every contrib migration applied (`admin` 0001–0003, `auth` 0001–0012, `contenttypes`, `sessions`).
  - `admin.0001_initial` depends on `swappable_dependency(AUTH_USER_MODEL)`, which resolves to `("accounts", "__first__")` after the swap.
  - Both `makemigrations` and `migrate` then fail in `MigrationLoader.check_consistent_history` with `InconsistentMigrationHistory`.
  - So the local DB must be deleted **before** `makemigrations accounts` runs.
- **Layout today (`base.html`):** the header holds the app name and `<nav>` with `<span>Goals</span><span>Log in</span>`. Messages render as a `<ul>` between the header and `<main>`. `home.html` extends it.
- **Tests:** `src/core/tests/test_home.py` holds a `PageParser(HTMLParser)` with these parts:
  - `text(section)` and `href_text()`, built on `collapse()`
  - the full `VOID_ELEMENTS`
  - `SECTIONS = ("title", "header", "nav", "main", "footer")`

  The class-level helper is `get_page()`.
  - The nav test asserts that "Goals" and "Log in" appear in the nav text and not in the link text. A real "Sign up" link or the username as plain text doesn't break it.
  - `PageParser` can be imported from other test modules. A non-`test_*` module keeps the runner from collecting it twice.
  - The runner forces `DEBUG=False`. The suite needs the local `.env` (`SECRET_KEY`). Single module: `./.venv/bin/python src/manage.py test accounts.tests.test_signup --verbosity 2`.
- **Django 6.1.1 auth internals** (from the source in `.venv`):
  - **`UserCreationForm`:**
    - `Meta.model` is the concrete `auth.User`. With a swapped model, `clean_username` (`self._meta.model.objects`) raises "Manager isn't available". So `class Meta(UserCreationForm.Meta): model = User` is required, and it is the documented pattern.
    - `clean_username` rejects case-insensitive duplicates with "A user with that username already exists." on `username`.
    - The mismatch error is "The two password fields didn’t match." (U+2019 apostrophe) on `password2`.
    - Validator errors also go on `password2`. `_post_clean` runs them against the instance, so the similarity validator sees the username.
    - The password widgets don't re-render values (`render_value=False`) and set `autocomplete="new-password"`.
  - **`login(request, user)`:**
    - With only `ModelBackend` configured, no `backend=` is needed.
    - It cycles the session key, rotates the CSRF token, and stores `_auth_user_id` (the pk as a string).
  - **`UserAdmin`:** works unchanged for an `AbstractUser` subclass. `ModelAdmin.get_form` rebuilds its forms for the registered model. The contrib `@admin.register(User)` skips swapped models, so there's no `AlreadyRegistered` clash.
  - **`LoginView`:**
    - It implements `redirect_authenticated_user` in `dispatch`.
    - It decorates `dispatch` with `sensitive_post_parameters()`, `csrf_protect` and `never_cache`.
    - Its default redirect is `resolve_url(settings.LOGIN_REDIRECT_URL)`. Django's own default for that is `/accounts/profile/`, so we must set it.
  - **`CreateView`:** `form_valid` sets `self.object = form.save()` before it builds the redirect, so a `form_valid` override can call `login(self.request, self.object)` after `super().form_valid(form)`.
  - **`makemigrations accounts`:** produces `0001_initial`, depending on `("auth", "0012_alter_user_first_name_max_length")`. It contains a `CreateModel` with the `AbstractUser` fields, M2M fields to `auth.Group` and `auth.Permission`, and `UserManager`.
  - **`assertFormError(form, field, errors)`:** takes the form object (`response.context["form"]`), not the response.
  - **Test passwords for username `alice`**, run against all four validators:

    | Password | Result |
    |---|---|
    | `Tr4ck-Learning!` | passes all four |
    | `password123` | fails only "This password is too common." |
    | `Xq7#vB` | fails only "This password is too short. It must contain at least 8 characters." |
- **Docs:**
  - `CLAUDE.md` has Stack (bullets), Commands (one bash block) and Layout (bullets).
  - `README.md` has Setup (bash block plus paragraphs), Tests and lint, Layout and Workflow.

## Design decisions
- **`accounts.User(AbstractUser)` with no body** (`pass` plus a docstring), with `AUTH_USER_MODEL = "accounts.User"` set in the same step as the model and its generated `0001_initial` migration. Django has no valid in-between state. All code reaches the user model through `get_user_model()` or `settings.AUTH_USER_MODEL`.
- **`admin.site.register(User, UserAdmin)`** in `accounts/admin.py`. `UserAdmin` needs no subclass, because there are no extra fields.
- **`SignUpForm(UserCreationForm)`** in `accounts/forms.py`, containing only `class Meta(UserCreationForm.Meta): model = User` (via `get_user_model()`). It keeps `fields = ("username",)`, and the two password fields come from the base form.
- **`SignUpView(CreateView)`** in `accounts/views.py`:
  - `form_class = SignUpForm`, `template_name = "accounts/signup.html"`
  - `get_success_url()` returns `resolve_url(settings.LOGIN_REDIRECT_URL)`
  - `form_valid` calls `super().form_valid(form)`, then `login(self.request, self.object)` and `messages.success(self.request, f"Welcome, {username}!")`, and returns the redirect
  - `dispatch` sends authenticated users to `resolve_url(settings.LOGIN_REDIRECT_URL)` before any form handling. This mirrors `LoginView.redirect_authenticated_user`.
  - `dispatch` is decorated with `sensitive_post_parameters("password1", "password2")`, so the passwords never show up in error reports. This mirrors `LoginView`. It is the one addition beyond the ACs, and it gets its own step.
- **Settings:** `LOGIN_REDIRECT_URL = "/"`, the value the ticket specifies. It is shared with #4's `LoginView`.
- **URLs:**
  - `accounts/urls.py` has `app_name = "accounts"` and `path("signup/", SignUpView.as_view(), name="signup")`.
  - `config/urls.py` adds `path("accounts/", include("accounts.urls"))`.
- **Template `src/templates/accounts/signup.html`:**
  - it extends `base.html`
  - it contains `<form method="post" action="{% url 'accounts:signup' %}">`, `{% csrf_token %}`, `{{ form }}` (Django's div form rendering, which includes the field errors) and a submit button
  - it uses simple Tailwind classes, matching the layout
- **Nav in `base.html`:** `<span>Goals</span>` for everyone, then:
  - logged in: `<span>{{ user.get_username }}</span>`
  - anonymous: `<span>Log in</span>` and `<a href="{% url 'accounts:signup' %}">Sign up</a>`
  - this is one `{% if user.is_authenticated %}` block, with autoescaping on
  - #2's nav test runs anonymously, so it keeps seeing "Goals" and "Log in" as non-links
- **Shared test helper:**
  - A test-only refactor moves `PageParser`, `collapse`, `VOID_ELEMENTS` and `SECTIONS` from `core/tests/test_home.py` to `src/core/tests/html.py`. The module is not named `test_*`, so the runner won't collect it twice. Both apps import it from there.
  - Later steps extend it with `links(section)`, which returns the `(href, text)` pairs in a section, and `elements`, the start tags with their attributes. That way AC3 and AC9 assert on structure, not on substrings.
- **Test data:** the module constants `USERNAME = "alice"`, `PASSWORD = "Tr4ck-Learning!"`, and the invalid examples from the research table. Where a test needs an existing user, only the case under test may collide with it, so one invalid input never triggers a second, unrelated error (see step 11). Logged-in cases use `self.client.force_login(user)`. Login state is checked as `self.client.session.get("_auth_user_id") == str(user.pk)`.
- **Migration drift guard:** a test runs `call_command("makemigrations", "--check", "--dry-run")`. A future change to `accounts.User` without its migration then fails the suite. This is cheap, and it protects the user model above all.

## Steps
Approved by the user on 2026-10-02. The approval includes:
- step 13 (`sensitive_post_parameters`), which goes beyond the ACs
- steps 3 and 11 as guard tests that pass on arrival, each checked with its mutations
- the one-time deletion of the local `src/db.sqlite3` in step 2
- the three review changes: logged-in users don't see "Log in", step 11's test data no longer collides, and the wording of steps 2 and 4 is cleaned up

Test files:
- `src/accounts/tests/test_apps.py` (`SimpleTestCase`) holds the app and settings checks.
- `src/accounts/tests/test_models.py` (`TestCase`) holds the user model, the migrations and the admin.
- `src/accounts/tests/test_signup.py` (`TestCase`) holds the sign-up view.
- `src/accounts/tests/test_nav.py` (`TestCase`) holds the nav.

Each step is one red–green–refactor cycle and one commit, `feat(auth-signup): <what the step delivers>`. Step 5 is a test-only refactor, committed as `refactor(auth-signup): ...`.

- [x] 1. The `accounts` app is installed: `apps.is_installed("accounts")` is `True`. Test: `src/accounts/tests/test_apps.py`, expected red `False is not True`. It also needs `src/accounts/tests/__init__.py`, and an empty `src/accounts/__init__.py` so discovery finds the tests, as in #2 step 1. Impl: `src/accounts/apps.py` (`AccountsConfig`, `name = "accounts"`), and `"accounts"` in `INSTALLED_APPS`. Covers: AC1.
- [x] 2. The project uses the custom user model:
  - `settings.AUTH_USER_MODEL == "accounts.User"`
  - `get_user_model()._meta.label == "accounts.User"`
  - it is a subclass of `AbstractUser`
  - `{f.name for f in User._meta.fields} == {f.name for f in AbstractUser._meta.fields} | {"id"}`, meaning no extra fields

  Checked 2026-10-02: an abstract model's `_meta.fields` works and lists the 10 concrete `AbstractUser` fields. The many-to-many fields aren't in `fields`.

  Test: `src/accounts/tests/test_models.py`, expected red `'auth.User' != 'accounts.User'`. Covers: AC2.
  - **Manual step, before the first `makemigrations`:** delete the local `src/db.sqlite3`. It is approved in the ticket and holds no data worth keeping. Otherwise `makemigrations` fails with `InconsistentMigrationHistory`.
  - Impl: `src/accounts/models.py` (`class User(AbstractUser)`), `AUTH_USER_MODEL = "accounts.User"` in `settings.py`, and `./.venv/bin/python src/manage.py makemigrations accounts`, which generates `src/accounts/migrations/0001_initial.py` (plus `migrations/__init__.py`).
  - After green, run `./.venv/bin/python src/manage.py migrate` to rebuild the local DB, and check that `showmigrations` lists `accounts.0001_initial` as applied.
- [x] 3. No model change is missing a migration: `call_command("makemigrations", "--check", "--dry-run", verbosity=0)` doesn't raise `SystemExit`. Test: `test_models.py`. Impl: none. Covers: AC2.
  - A guard test that passes on arrival, because step 2 generated the migration. Confirm that it guards by temporarily adding a field, e.g. `nickname = models.CharField(max_length=20, blank=True)`, to `accounts.User`: the test must go red. Then remove the field.
  - Done 2026-10-02: green on arrival. With a temporary `nickname` field on `accounts.User`, this test went red ("A model change has no migration"), and so did step 2's no-extra-fields test. The field was removed and no migration file was written (`--dry-run`).
- [ ] 4. The user model is registered in the admin with `UserAdmin`: `isinstance(admin.site._registry[get_user_model()], UserAdmin)`. Test: `test_models.py`, `assertIsInstance(admin.site._registry.get(get_user_model()), UserAdmin)`, expected red `None is not an instance of <class 'UserAdmin'>`. Impl: `src/accounts/admin.py`. Covers: AC2.
- [ ] 5. Test-only refactor: move `VOID_ELEMENTS`, `SECTIONS`, `collapse` and `PageParser` from `src/core/tests/test_home.py` to `src/core/tests/html.py`, and import them in `test_home.py` from there. Test: the whole suite stays green, with the same number of tests (33). No new test. Impl: none. Covers: AC3, AC9 and AC10 (prerequisite). Commit: `refactor(auth-signup): share the page parser between apps' tests`.
- [ ] 6. An anonymous `GET /accounts/signup/` returns 200 and is routed through the `accounts.urls` include:
  - `reverse("accounts:signup") == "/accounts/signup/"`
  - the root URLconf has a `URLResolver` with `urlconf_name is accounts.urls`, `namespace == "accounts"` and `str(pattern) == "accounts/"`
  - `accounts/signup.html` and `base.html` are both used

  Test: `src/accounts/tests/test_signup.py`. Its first assertion is the status on the literal path `/accounts/signup/`, so the red is `404 != 200`, not a `NoReverseMatch` error. Impl: `src/accounts/urls.py` (`app_name`, `signup`); `SignUpView` as a minimal `TemplateView(template_name="accounts/signup.html")`; `src/templates/accounts/signup.html`, which extends `base.html` with an empty content block; and the `include` in `config/urls.py`. Covers: AC1, AC3 (status, templates).
- [ ] 7. The page renders the sign-up form:
  - `list(response.context["form"].fields) == ["username", "password1", "password2"]`
  - `response.context["form"]._meta.model is get_user_model()`
  - the HTML has a `<form>` with `method="post"` and `action == reverse("accounts:signup")`, an `<input name="csrfmiddlewaretoken">`, and an `<input name=...>` for each of the three fields

  Test: `test_signup.py`, expected red `KeyError: 'form'`. Write that check as `assertIn("form", response.context)` so the red is an assertion. Impl: `src/accounts/forms.py` (`SignUpForm`); `SignUpView.get_context_data` adds `form=SignUpForm()` (still a `TemplateView`, so `POST` is not handled yet); the form markup in `signup.html`; and `PageParser.elements`, a list of `(tag, attrs dict)`, in `core/tests/html.py`. Covers: AC3.
- [ ] 8. A valid `POST` creates exactly one user with a hashed password:
  - `get_user_model().objects.count() == 1`
  - `user.username == "alice"`
  - `user.check_password(PASSWORD)`
  - `user.password != PASSWORD`

  Test: `test_signup.py`, expected red `0 != 1`, because a `TemplateView` answers `POST` with 405. Impl: `SignUpView` becomes a `CreateView` (`form_class = SignUpForm`, `template_name`), and `get_context_data` is dropped. It gets a minimal `success_url = "/"`, so the redirect works. Covers: AC4.
- [ ] 9. After a valid `POST` the new user is logged in and redirected to `LOGIN_REDIRECT_URL`:
  - `settings.LOGIN_REDIRECT_URL == "/"`
  - `self.client.session["_auth_user_id"] == str(user.pk)`
  - `assertRedirects(response, settings.LOGIN_REDIRECT_URL, fetch_redirect_response=False)`

  Test: `test_signup.py`, expected red: `_auth_user_id` is not in the session (an assertion via `session.get`). Impl:
  - `LOGIN_REDIRECT_URL = "/"` in `settings.py`
  - `SignUpView.form_valid` calls `login()`
  - `get_success_url` returns `resolve_url(settings.LOGIN_REDIRECT_URL)`, which replaces the hard-coded `success_url`

  Covers: AC5.
- [ ] 10. Following the redirect, the home page shows "Welcome, alice!": a `POST` with `follow=True` lands on `/`, and that page contains the message. Test: `test_signup.py`. Impl: `messages.success(...)` in `form_valid`. Covers: AC6.
- [ ] 11. An invalid `POST` re-renders the form with the error on the right field, creates no user, logs no one in, and doesn't echo the submitted passwords. It uses one `subTest` per case. Each case asserts:
  - status 200 and `accounts/signup.html` used
  - `assertFormError(response.context["form"], <field>, <message>)`
  - the user count is unchanged
  - `"_auth_user_id"` is not in the session
  - `assertNotContains` for each submitted password value

  `setUp` creates the existing user `alice` (`create_user`), so "user count unchanged" means it stays at 1. Only the two duplicate cases submit `alice` or `Alice`. The other three submit `bob`, so they can't also trigger the duplicate-username error. The cases are:

  | Case | Username | Passwords | Error |
  |---|---|---|---|
  | mismatch | `bob` | `Tr4ck-Learning!` / `Different-Pass9!` | `password2`: "The two password fields didn’t match." |
  | exact duplicate | `alice` | `Tr4ck-Learning!` twice | `username`: "A user with that username already exists." |
  | case-only duplicate | `Alice` | `Tr4ck-Learning!` twice | `username`: same message |
  | common | `bob` | `password123` twice | `password2`: "This password is too common." |
  | short | `bob` | `Xq7#vB` twice | `password2`: "This password is too short. It must contain at least 8 characters." |

  Every case also asserts that its error is the only one on the form (`form.errors` has just that field), which proves the data doesn't collide.

  Test: `test_signup.py`. Impl: none. Covers: AC7.
  - A guard test that passes on arrival, because `CreateView` and `UserCreationForm` already behave this way, and AC7 pins that behaviour.
  - Confirm that it guards with two temporary mutations, then revert both:
    1. Base `SignUpForm` on `BaseUserCreationForm`, which has no case-insensitive check. The case-only subtest must go red.
    2. Give `password1` a `PasswordInput(render_value=True)`. The no-echo assertion must go red.
- [ ] 12. A logged-in user is redirected away from sign-up. After `force_login(existing_user)`:
  - `GET /accounts/signup/` redirects to `settings.LOGIN_REDIRECT_URL` (`fetch_redirect_response=False`), and `accounts/signup.html` is not used
  - a valid `POST` for a new username also redirects there, and the user count is unchanged

  Test: `test_signup.py`, expected red `200 != 302` on the `GET`. Impl: `SignUpView.dispatch` returns `redirect(resolve_url(settings.LOGIN_REDIRECT_URL))` for authenticated users. Covers: AC8.
- [ ] 13. Sign-up `POST`s are marked as sensitive, so the passwords are hidden from error reports: after a `POST`, `response.wsgi_request.sensitive_post_parameters == ["password1", "password2"]`. Test: `test_signup.py`, expected red: an `AttributeError` turned into an assertion with `getattr(..., None)`. Impl: `@method_decorator(sensitive_post_parameters("password1", "password2"), name="dispatch")` on `SignUpView`. Covers: none (security hygiene beyond the ACs, mirroring `LoginView`).
- [ ] 14. The nav depends on whether the visitor is logged in:
  - anonymous `GET /`: `page.links("nav") == [(reverse("accounts:signup"), "Sign up")]`, and "Goals" and "Log in" are in `page.text("nav")` but not in the link text
  - after `force_login`: `page.links("nav") == []`, "Goals" is in `page.text("nav")`, and "Log in" is not

  Test: `src/accounts/tests/test_nav.py`, two tests (anonymous, logged in). The expected red for the anonymous test is `[] != [('/accounts/signup/', 'Sign up')]`. The logged-in test fails as well, because "Log in" is still shown, so both go red for real. Impl: the `{% if user.is_authenticated %}…{% else %}<span>Log in</span><a href="{% url 'accounts:signup' %}">Sign up</a>{% endif %}` block in `base.html`, and `PageParser.links(section)` in `core/tests/html.py`. Covers: AC9.
- [ ] 15. Logged-in users see their username in the nav, and anonymous visitors don't. A user `alice` exists in both cases:
  - after `force_login`, `"alice"` is in `page.text("nav")`
  - anonymous, `"alice"` is not in `page.text("nav")`

  Test: `test_nav.py`, expected red `'alice' not found in 'Goals'`. Impl: `<span>{{ user.get_username }}</span>` in the authenticated branch of `base.html`. Covers: AC10.
- [ ] 16. Docs. No test. Commit `docs(auth-signup): document the accounts app and the custom user model`.
  - In `CLAUDE.md`, add to Stack: auth uses the custom user model `accounts.User` (`AUTH_USER_MODEL`), and code always refers to it through `get_user_model()` or `settings.AUTH_USER_MODEL`, never `django.contrib.auth.models.User`. Profile data goes on `Profile`, not on `User`. `LOGIN_REDIRECT_URL = "/"`.
  - In `CLAUDE.md`, add to Layout: `src/accounts/` (custom user model, sign-up at `/accounts/signup/`; #4 adds log-in and log-out under `/accounts/`).
  - In `README.md`, add the same Layout entry, plus a short note after Setup: a checkout from before `auth-signup` must delete `src/db.sqlite3` once and re-run `migrate`, because the user model changed.
  - Manual check before committing:
    - `migrate` on the fresh DB succeeds
    - `createsuperuser` creates an `accounts.User`
    - in `runserver`, `/accounts/signup/` signs up a new user, who lands on `/` with "Welcome, <name>!" and sees their username in the nav
    - `/admin/` lists Users under Accounts

## Coverage
| AC | Steps |
|---|---|
| AC1 `accounts` app installed; URLs under `/accounts/` with the namespace; `reverse` | 1, 6 |
| AC2 custom user model `accounts.User`, no extra fields, `UserAdmin` | 2, 3, 4 |
| AC3 anonymous `GET` 200, template extends base, form fields, CSRF, `method`/`action` | 6, 7 |
| AC4 valid `POST` creates one user, hashed password | 8 |
| AC5 logged in and redirected to `LOGIN_REDIRECT_URL` (`"/"`) | 9 |
| AC6 "Welcome, <username>!" after the redirect | 10 |
| AC7 invalid `POST`: field errors, no user, no login, no echoed passwords (5 cases) | 11 |
| AC8 logged-in `GET`/`POST` redirected, no user created | 12 |
| AC9 anonymous: Goals · Log in · "Sign up" link; logged in: Goals only (no "Log in", no link); placeholders stay non-links | 14 |
| AC10 username in the nav for logged-in users only | 15 |

Step 13 is beyond the ACs: `sensitive_post_parameters`, as Django's own auth views do. Step 5 is a test-only refactor. Step 16 covers what tests can't verify: docs, the one-time DB reset note, and the manual check, including `createsuperuser` and the admin.
