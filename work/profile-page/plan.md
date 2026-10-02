# Plan: profile-page

## Research summary
- **Project (from #3–#5):**
  - Templates live in `src/templates/` (`TEMPLATES["DIRS"]`; `APP_DIRS` is also on). Form pages extend `base.html`, render `{{ form }}` inside `<form method="post" action="{% url … %}">` with `{% csrf_token %}`, and use only `h1 class="text-2xl font-bold"` for styling.
  - URL modules set `app_name` and use `path("…/", View.as_view(), name=…)`, mounted from `config/urls.py` with `include()`.
  - Views set success messages in `form_valid` after `super()`, and redirect targets come from `resolve_url`/`reverse`.
  - `LOGIN_URL = "accounts:login"`. There is no `LoginRequiredMiddleware` and nothing uses `login_required` yet.
  - `profiles` has `Profile` (`user` one-to-one `related_name="profile"`, `name` 100 blank, `cohort` 50 blank, `focus_areas` M2M to `tags.Tag`), the signal, and the admin inline. It has no views, URLs, forms or templates.
  - `tags/models.py`:
    - `strip()` strips only strings.
    - `TagManager.get_or_create_by_name` does `strip`, then an `iexact` lookup, then `full_clean(validate_constraints=False)`, then `save()` inside a savepoint with `IntegrityError` recovery.
    - `Tag.clean_fields` and `Tag.save` strip.
    - `Meta.ordering = ("name",)`, and `UniqueConstraint(Lower("name"))`.
  - Class-level options are tuples (ruff RUF012).
- **Base nav (`base.html:13-25`):**
  - `<span>Goals</span>`, then for logged-in users `<span class="font-medium text-slate-800">{{ user.get_username }}</span>` and the logout `<form>`; otherwise the Log in and Sign up links.
  - `accounts/tests/test_nav.py` pins the logged-in nav: `links("nav") == []` and `text("nav") == "Goals alice Log out"`.
- **Tests:**
  - `PageParser`:
    - `text(section)` includes link text.
    - `forms(section)` returns `<input>` attribute dicts, including `value`; `<select>`/`<textarea>` appear only in `elements`.
    - `convert_charrefs=True` unescapes entities, so escaping must be checked on the raw response (`assertNotContains`).
  - Form errors follow the `test_signup.py` pattern:
    - status 200 and the template
    - `assertFormError(form, field, message)`
    - the message in `page.text("main")`
  - CSRF follows `test_logout.CsrfTests`: `Client(enforce_csrf_checks=True)`, a GET first so the cookie is set, and the token read from the rendered form, with a `len(tokens) == 1` assertion rather than tuple-unpacking.
  - Per-module constants `USERNAME = "alice"` and `PASSWORD = "Tr4ck-Learning!"`, and `force_login` unless the login flow itself is tested.
  - First reds must be assertions. A new URL's first test hits a **literal path** and asserts the status first (`404 != 200`); `reverse()` of the new names comes after that assertion. Guards that pass on arrival each name a mutation that must turn them red.
- **Django 6.1.1 and Python 3.14 (verified by probes):**
  - **Login redirect:** `LoginRequiredMixin` sends an anonymous `GET` or `POST` to `302 /accounts/login/?next=/profile/5/`, with the query string URL-encoded into `next`. With `Client(enforce_csrf_checks=True)` and no token, an anonymous POST gets 403, because CSRF runs first.
  - **Scoped lookup:** `SingleObjectMixin.get_object` filters `get_queryset()` by pk and raises `Http404`. `BaseUpdateView.get` and `.post` call `get_object()` before validating, so a scoped queryset gives 404 for another user's pk on GET and POST, and nothing is saved.
  - **Required name:** a `ModelForm` field keeps the model's `max_length=100` and `strip=True`. Setting `self.fields["name"].required = True` in `__init__` makes `"   "` "This field is required.". The length error reads "Ensure this value has at most 100 characters (it has 101).".
  - **Unicode:**
    - `normalize("NFKC", "ＰＹＴＨＯＮ") == "PYTHON"`.
    - NFKC composes `"café"` into `"café"`.
    - `category("\x00") == "Cc"`; `category("​") == category("﻿") == "Cf"`.
    - `" ".join(s.split())` collapses whitespace, including `\t\n\x0b\x0c\r\x1c-\x1f\x85` and U+00A0, U+2028 and U+3000. No Cf character is treated as whitespace, so after collapsing, any remaining Cc/Cf characters (e.g. `\x00`, `\x7f`, U+200B, U+FEFF) can be rejected predictably.
  - **SQLite `LIKE` limit:** `name__iexact` with a 50,001-character value raises `OperationalError: LIKE or GLOB pattern too complex`, so validation must come before the lookup.
  - **Messages:** `messages.success` survives the redirect with `FallbackStorage` (`follow=True` shows "Profile saved.").
  - **Escaping:** `{{ profile.name }}` and a form `value` render `<script>` as `&lt;script&gt;`.

## Design decisions
- **URLs:** `src/profiles/urls.py` with `app_name = "profiles"`, mounted at `path("profile/", include("profiles.urls"))`.
  - `""` → `MyProfileView` (`mine`)
  - `"<int:pk>/"` → `ProfileDetailView` (`detail`)
  - `"<int:pk>/edit/"` → `ProfileUpdateView` (`edit`)
- **Ownership in one place:** `OwnProfileMixin(LoginRequiredMixin)` with `model = Profile` and `get_queryset()` returning `Profile.objects.filter(user=self.request.user)`. Both the detail and update views use it. Another user's pk and a missing pk both raise `Http404`, on GET and POST.
- **`MyProfileView(LoginRequiredMixin, RedirectView)`:** gets the profile with `Profile.objects.get_or_create(user=request.user)`, which covers users loaded from fixtures (CLAUDE.md), and redirects to its detail URL.
- **`ProfileUpdateView`:** uses `form_class = ProfileForm`, adds `messages.success(request, "Profile saved.")` in `form_valid`, and its success URL is the detail page.
- **`ProfileForm(ModelForm)`:** `Meta.fields = ("name", "cohort")`, plus a non-model field `focus_areas = forms.CharField(required=False)`.
  - `__init__` sets `name` as required, and sets the initial `focus_areas` to `", ".join(t.name for t in instance.focus_areas.all())`, in name order.
  - `clean_focus_areas()`:
    - split on `","`
    - normalise each entry with `Tag.objects.clean_name()`
    - drop empty entries
    - de-duplicate, keeping the first entry (comparing `casefold()`)
    - collect each failing entry's messages as `“<entry>”: <message>`, and raise one `ValidationError` listing them

    It creates **nothing**.
  - `save()` runs inside `transaction.atomic()`: it saves the instance, then `focus_areas.set(Tag.objects.get_or_create_by_name(n)[0] for n in cleaned names)`. Because validation happens in `clean`, any error leaves the database unchanged (AC8).
- **Tag normalisation (in `tags`):**
  - `normalize_name(value)` replaces `strip()`. For strings it applies NFKC, then `" ".join(value.split())` (trims and collapses whitespace); other values pass through unchanged. `Tag.clean_fields`, `Tag.save` and the manager all call it.
  - A field validator, `reject_invisible_characters`, on `Tag.name` raises `ValidationError("Tag names can't contain control or invisible characters.")` for any character in Unicode categories Cc or Cf. It needs a migration (`AlterField`).
  - `TagManager.clean_name(name) -> str` normalises, then runs `Tag(name=…).clean_fields()` (no DB access) and returns the normalised name, or raises `ValidationError`.
  - `get_or_create_by_name` calls `clean_name()` **before** its lookup, so over-long or invalid names never reach SQLite's `LIKE`.
- **Templates:** `src/templates/profiles/profile_detail.html` and `profile_form.html` extend `base.html`. The detail page has a `<dl>` with Name, Cohort and Focus areas (a `<ul>` of tags), placeholders, and an "Edit profile" link. The form page renders `{{ form }}`, following the signup pattern.
- **Nav:** the username `<span>` becomes `<a href="{% url 'profiles:mine' %}" class="font-medium text-slate-800 hover:underline">{{ user.get_username }}</a>`. The logged-in nav test is rewritten deliberately in the same step.
- **Reds for new views** come from literal paths (`/profile/`, `/profile/<pk>/`, `/profile/<pk>/edit/`). In step 8, the expected red is Django's `ImproperlyConfigured` ("No URL to redirect to"), because the update view doesn't redirect yet. That is the missing behaviour itself, like the accepted `AttributeError` red in #5.

## Steps
The user approved this plan on 2026-10-02.

Each step is one red–green–refactor cycle and one commit, `feat(profile-page): …`. Test modules:
- `src/profiles/tests/test_views.py`: the views, with one class per page
- `src/profiles/tests/test_forms.py`: focus-area parsing, through the view
- `src/tags/tests/test_models.py`: normalisation
- `src/accounts/tests/test_nav.py`: the nav

Guard steps (7, 14, 15, 16) pass on arrival and name their mutation.

- [x] 1. Your own profile page is served. Logged in as alice, `GET /profile/<alice.profile.pk>/`.
  - The status is **asserted first** (200).
  - `profiles/profile_detail.html` and `base.html` are used.
  - `reverse("profiles:detail", args=[pk]) == f"/profile/{pk}/"`.

  Expected red: `404 != 200`. Impl:
  - `profiles/urls.py` with the `detail` route, and the `path("profile/", include(...))` in `config/urls.py`
  - `ProfileDetailView(DetailView)` with `model = Profile` (no login or scoping yet)
  - a template with an empty `<dl>`

  Covers: AC1 (detail), AC4.
- [x] 2. The detail page shows the profile's values. Subtests:
  - **filled:** name "Alice Smith", cohort "Spring 2026", tags "Python" and "Django". `page.text("main")` contains them, with "Django" before "Python".
  - **empty:** `main` shows "Not set" twice and "No focus areas yet.".

  Expected red: the values are missing from `main`. Impl: the template's `<dl>` and placeholders. Covers: AC4.
- [x] 3. The detail page requires login. An anonymous `GET /profile/<pk>/` redirects to `f"{resolve_url(settings.LOGIN_URL)}?next=/profile/<pk>/"` (`fetch_redirect_response=False`). Expected red: `200 != 302`. Impl: `LoginRequiredMixin` on the detail view. Covers: AC2 (detail).
- [x] 4. Another user's profile, and an id that doesn't exist, are 404 on the detail page. Bob, logged in, requests alice's detail URL, and then `pk=999999`. Both return 404, and the first response contains neither alice's name nor her cohort. Expected red: `200 != 404`. Impl: `OwnProfileMixin` (the scoped `get_queryset`) used by the detail view. Covers: AC5 (detail).
- [x] 5. `/profile/` sends you to your own profile. Logged in:
  - `GET /profile/` returns 302, **asserted first**, to alice's detail URL.
  - `reverse("profiles:mine") == "/profile/"`.

  Subtests:
  - **a user without a profile** (`save_base(raw=True)`, as `loaddata` does): the request creates exactly one profile and redirects to it
  - **anonymous:** redirected to login with `next=/profile/`

  Expected red: `404 != 302`. Impl: `MyProfileView(LoginRequiredMixin, RedirectView)` with `get_or_create`, and the `mine` route. Covers: AC1 (mine), AC2 (mine), AC3.
- [x] 6. The edit page renders a pre-filled form. For alice, whose name is "Alice" and whose tags are "Python" and "Django":
  - `GET /profile/<pk>/edit/` returns 200, **asserted first**, and `profiles/profile_form.html` is used.
  - `reverse("profiles:edit", args=[pk])` matches.
  - `forms("main")` has exactly one form, with `method="post"` and the edit URL as `action`.
  - Its inputs include `csrfmiddlewaretoken`, `name` with value "Alice", `cohort` and `focus_areas` with value "Django, Python".
  - The detail page's `main` links "Edit profile" to the edit URL.

  Expected red: `404 != 200`. Impl:
  - `profiles/forms.py` `ProfileForm`: the fields, required `name` and the initial `focus_areas`, but no parsing yet
  - `ProfileUpdateView(OwnProfileMixin, UpdateView)` and the `edit` route
  - the `profile_form.html` template, and the Edit link in the detail template

  Covers: AC1 (edit), AC4 (link), AC6.
- [x] 7. The edit page is login-required and scoped. Subtests:
  - **anonymous** `GET` and `POST` to alice's edit URL: redirected to login with `next`, and the name is unchanged
  - **bob** `GET` and `POST` (`name="hacked"`) to alice's edit URL: 404 both times, alice's name is unchanged, and the 404 page contains none of alice's values

  Impl: none, because `OwnProfileMixin` from step 6 already covers it. Covers: AC2 (edit), AC5 (edit).
  - Guard. Mutation: the update view uses `LoginRequiredMixin, UpdateView` with `model = Profile` (unscoped) instead of `OwnProfileMixin`. The bob subtests must go red. Revert afterwards.
  - Done 2026-10-02: green on arrival, after one deliberate test fix. The first draft sent `{"name": "hacked"}` with the GET too, which put it in the query string and so in `next`. Now only the POST carries data.
  - Under the mutation, both bob subtests went red: GET `200 != 404`, and the POST errored because the unscoped view accepted the save. The view was then restored.
- [x] 8. A valid save stores trimmed values and redirects with a message. POST `name="  Alice Smith "`, `cohort=" Spring 2026 "` and `focus_areas=""`. Assert:
  - a redirect to the detail URL
  - the stored values are trimmed
  - with `follow=True`, the page shows "Profile saved."

  Expected red: `ImproperlyConfigured` (no URL to redirect to). Impl: `get_success_url` set to the detail URL, and `form_valid` adding the message. Covers: AC7.
  - Done 2026-10-02: red as `AttributeError: 'Profile' object has no attribute 'get_absolute_url'`. That is Django 6.1's form of "no URL to redirect to", not the `ImproperlyConfigured` the plan named, but it is the same missing behaviour. Then green.
- [x] 9. The focus areas are set from the comma-separated text. With an existing tag "Python" and alice's profile holding "Django", POST `focus_areas=" python , Machine Learning,, MACHINE learning , "`. Assert:
  - alice's tags are exactly ["Machine Learning", "Python"]
  - the existing "Python" row is reused, and its spelling is kept
  - "Machine Learning" is created once
  - "Django" was removed from the profile, but the `Tag` "Django" still exists

  Expected red: the tags are unchanged. Impl: `ProfileForm.clean_focus_areas` (split, `strip()` for now, drop empty entries, de-duplicate by `casefold`) and `save()` (`transaction.atomic` and `focus_areas.set(...)` via `get_or_create_by_name`). Covers: AC7.
- [x] 10. Invalid input re-renders the form and saves nothing. Subtests on alice's edit URL, each checking:
  - status 200 and the form template
  - `assertFormError(form, field, message)`, with the message in `page.text("main")`
  - alice's name, cohort and tags unchanged, and `Tag.objects.count()` unchanged

  The cases:
  - `name=""` and `name="   "` → `name`: "This field is required."
  - a 101-character name → `name`: "Ensure this value has at most 100 characters (it has 101)."
  - a 51-character cohort → `cohort`: the 50 version of that message
  - `focus_areas="Valid, <51 × x>"` → a `focus_areas` error containing the 51-character entry and "at most 50 characters". No "Valid" tag is created.

  Expected red: a blank name is accepted (`302 != 200`). Impl:
  - `TagManager.clean_name()`, which strips and runs `Tag(name=…).clean_fields()` with no DB access and returns the name
  - `clean_focus_areas` using it and raising entry-named errors
  - `name` was already required in step 6, so only the field-level checks are new

  Covers: AC8.
  - Done 2026-10-02.
  - **Correction to the plan's expected red:** the name and cohort cases were already green. `name` became required in step 6, and the `ModelForm` gives the length errors.
  - The red came from the over-long focus-area entry. The save raised an unhandled `ValidationError` (a 500 in a real request) instead of a form error. That is the missing validation itself.
  - Then green, with `Tag.objects.clean_name()` and entry-named errors in `clean_focus_areas`.
- [x] 11. Tag names are NFKC-normalised and their whitespace collapsed. Test: `tags/tests/test_models.py`. With "Python" saved:
  - `get_or_create_by_name("ＰＹＴＨＯＮ")` returns `(python, False)`
  - `get_or_create_by_name("café")`, then `("café")`, gives one tag (the second call has `created=False`)
  - `get_or_create_by_name("Machine \t  Learning")` stores "Machine Learning"
  - `Tag.objects.create(name=" Data  Science ")` stores "Data Science"

  Expected red: a new tag is created for "ＰＹＴＨＯＮ" (`True is not False`). Impl: `normalize_name()` (NFKC plus split/join) replaces `strip()` in `clean_fields`, `save` and `clean_name`. Covers: AC9.
- [x] 12. Control and invisible characters are rejected. Test: `tags/tests/test_models.py`. Subtests over `"Py\x00thon"`, `"Python​"` and `"﻿Python"`:
  - `get_or_create_by_name(…)` raises `ValidationError` with "Tag names can't contain control or invisible characters.", and the tag count is unchanged.
  - In `profiles/tests/test_forms.py`, posting `focus_areas="Python​"` to the edit view gives a `focus_areas` error with that message, and nothing is saved.

  Expected red: no `ValidationError`. Impl: the `reject_invisible_characters` validator on `Tag.name`, and `makemigrations tags` creates `0003`. Covers: AC8, AC9.
  - Done 2026-10-02: red as expected (`ValidationError not raised` ×3, and the form returned `302 != 200`), then green.
  - The tests write the invisible characters as escapes (`\u200b`, `\ufeff`, `\u0301`, `\u00a0`). Ruff's PLE2515 flags literal ones, which had slipped into the step 11 test as well; they were converted here.
- [x] 13. The name is validated before the lookup. `get_or_create_by_name("x" * 50_001)` raises `ValidationError`, not a database error, and creates nothing. Expected red: `OperationalError: LIKE or GLOB pattern too complex` (the missing behaviour itself). Impl: `get_or_create_by_name` calls `clean_name()` first, and the `iexact` lookup uses the validated name. Covers: AC9.
  - Done 2026-10-02: red as expected (`OperationalError: LIKE or GLOB pattern too complex`), then green. `clean_name()` now does the field validation, so the later `full_clean(validate_constraints=False)` call was dropped; uniqueness stays with the database.
- [x] 14. CSRF is enforced on the edit form. Test: `test_views.py`, with `Client(enforce_csrf_checks=True)` and `force_login(alice)`, after a GET of the edit page (so the cookie is set):
  - a POST without a token returns 403, and the name is unchanged
  - a POST with the `csrfmiddlewaretoken` read from that page's form (asserting `len(tokens) == 1`) returns 302, and the name is saved

  Impl: none. Covers: AC6 (CSRF).
  - Guard. Mutation: `@method_decorator(csrf_exempt, name="dispatch")` on `ProfileUpdateView`. The first case must go red. Revert afterwards.
  - Done 2026-10-02: green on arrival. Under the mutation, the no-token case went red (`302 != 403`). The view was then restored.
- [x] 15. Your pages never show other users' data. Test: `test_views.py`.
  - Alice has name "Alice Only", cohort "Cohort A", and tags "Python" (shared) and "Haskell" (alice only).
  - Bob has "Bob", "Cohort B" and "Python".
  - Bob's detail page and edit page contain none of "Alice Only", "Cohort A" or "Haskell".
  - The edit page has no `select` element and no `input type="checkbox"` (checked in `page.elements`).

  Impl: none. Covers: AC10.
  - Guard. Mutation: `ProfileForm.focus_areas = forms.ModelMultipleChoiceField(queryset=Tag.objects.all(), required=False)`. It must go red, because a `<select>` appears and "Haskell" shows on bob's page. Revert afterwards.
  - Done 2026-10-02: green on arrival. Under the mutation, both tests went red: a `select` element appeared, and "Haskell" was found on bob's edit page. The form was then restored.
- [x] 16. Profile values are escaped.
  - Alice's name, cohort and one tag are set to `<script>alert(1)</script>` (the tag through `Tag.objects.create`).
  - Her detail and edit responses: `assertNotContains(response, "<script>alert(1)</script>")` and `assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")`.

  Test: `test_views.py`. Impl: none. Covers: AC12.
  - Guard. Mutation: `{{ profile.name|safe }}` in the detail template. The detail subtest must go red. Revert afterwards.
  - Done 2026-10-02: green on arrival. Under the mutation, the detail subtest went red (the raw `<script>alert(1)</script>` was found). The template was then restored.
- [x] 17. The username in the nav links to your profile. Rewrite `test_logged_in_nav_has_username_and_logout_form_and_no_auth_links` to assert:
  - `links("nav") == [(reverse("profiles:mine"), USERNAME)]`
  - the text is still exactly "Goals alice Log out"
  - the logout form is unchanged

  Rename the test to `test_logged_in_nav_links_the_username_to_the_profile_and_has_logout`. The anonymous nav test is unchanged. Expected red: `[] != [('/profile/', 'alice')]`. Impl: the `<a>` in `base.html`. Covers: AC11.
  - This deliberately changes #4 AC10 ("no links" when logged in), recorded in the step note and the commit body.
  - Done 2026-10-02: red as expected (`[] != [('/profile/', 'alice')]`), then green with the `<a>` in `base.html`. The exact nav text and the logout-form assertions were unchanged, and so was the anonymous nav test.
- [x] 18. Docs. No test. Commit `docs(profile-page): document the profile pages and tag normalisation`.
  - `CLAUDE.md`:
    - **Stack, auth bullet:** the profile pages (`/profile/` redirects to your own, `/profile/<pk>/` and `/profile/<pk>/edit/` are login-required), and any view taking a pk must scope its queryset to `request.user` (`OwnProfileMixin`), so others' ids are 404.
    - **Tags bullet:** names are NFKC-normalised with whitespace collapsed; control and invisible characters are rejected; `Tag.objects.clean_name()` validates without touching the DB; and `get_or_create_by_name` validates before its lookup.
    - **Layout:** `src/profiles/` gains views, URLs and forms, and `src/templates/` gains `profiles/` pages.
  - `README.md`: the profile paragraph mentions `/profile/` and editing focus areas as comma-separated text. Update the Layout lines.
  - **Manual check:** against `runserver` with curl and a cookie jar, using two throwaway users:
    - log in as A, follow `/profile/`, edit with tags "Python, Django", and see "Profile saved."
    - log in as B and request A's `/profile/<pk>/` and `/edit/`: both 404
    - delete the throwaway users afterwards
  - Done 2026-10-02. Results against `runserver` with curl, a cookie jar per user and real CSRF tokens:
    - `migrate` applied `tags.0003_alter_tag_name` to the dev DB.
    - Anonymous `/profile/` gave 302 to `/accounts/login/?next=/profile/`.
    - For mc-alice, `/profile/` gave 302 to `/profile/3/`. Saving name "MC Alice" with focus areas "Python, Django, python" gave 302 back, and the page showed "Profile saved.", the name and the two tags (Django, Python).
    - The nav username linked to `/profile/`.
    - mc-bob got 404 for alice's detail, for her edit page and for a POST to it, and alice's name was unchanged.
    - The throwaway users and their two tags were deleted (0 users, 0 tags left).

### Review findings (final-review 2026-10-02, verdict FAIL; see `review.md`)
Each step is one cycle and one commit. Steps 21 and 23 are guards and test hardening, so they name their mutations.

- [x] 19. (Finding 1, high; AC13) Focus-area input is bounded before any database work. Test: `profiles/tests/test_forms.py`. Subtests on alice's edit URL:
  - `focus_areas` of 1,001 characters gives "Ensure this value has at most 1000 characters (it has 1001)."
  - 21 distinct entries (`"t1, t2, …, t21"`) give "You can have at most 20 focus areas."

  Each subtest asserts:
  - status 200 and `assertFormError` on `focus_areas`
  - the profile is unchanged and `Tag.objects.count()` is unchanged

  It also asserts that 20 entries are accepted (302, 20 tags). Expected red: 21 entries are accepted (`302 != 200`). Impl:
  - `max_length=1000` on the form field
  - in `clean_focus_areas`, after de-duplication and before returning, raise the count error when there are more than `MAX_FOCUS_AREAS = 20` names. `clean_name` does no DB work, so nothing touches the DB before this check.

  Covers: AC13.
- [x] 20. (Finding 2, medium; AC7, AC9) Full-width commas separate entries, and tag names can't contain commas.
  - **Test:** in `test_forms.py`, POSTing `focus_areas="Python\uff0cDjango"` gives exactly the tags ["Django", "Python"].
  - **Test:** in `tags/tests/test_models.py`, `get_or_create_by_name("a,b")` raises `ValidationError` "Tag names can't contain commas." and creates nothing.

  Expected red: one tag "Python,Django". Impl:
  - `clean_focus_areas` applies `unicodedata.normalize("NFKC", …)` to the whole text before splitting on `","`
  - a `reject_commas` validator on `Tag.name`, with `makemigrations tags` creating `0004`

  Covers: AC7, AC9.
- [x] 21. (Finding 3, medium; AC7) Entries that differ only in non-ASCII case are merged in the form. Test: in `test_forms.py`, POSTing `focus_areas="\u00c9lan, \u00e9lan"` gives exactly one tag, "Élan", and exactly one new `Tag` row. Impl: none, because `casefold` de-duplication already exists.
  - Guard. Mutation: replace `if name.casefold() not in seen:` with `if True:`. It must go red (two tags). Revert afterwards.
  - Done 2026-10-02: green on arrival. Under the mutation it went red, with two tags ('Élan', 'élan'). The form was then restored.
- [x] 22. (Finding 4) `ProfileForm` behaves as a normal `ModelForm`. Test: `test_forms.py`.
  - `ProfileForm()` with no instance renders: `str(form)` doesn't raise, and the initial `focus_areas` is `""`.
  - For alice's profile, a bound valid form with `save(commit=False)` doesn't change her tags until `form.save_m2m()` is called. After that call the tags are set.

  Expected red: `ValueError` from the unbound form (`…needs to have a value for field "id"…`). Impl:
  - compute the initial `focus_areas` only when `self.instance.pk` is set
  - move the `set()` into an override of `_save_m2m()`, which Django calls on `save(commit=True)` or from `save_m2m()`
  - keep `save()` atomic

  Covers: AC7.
  - Done 2026-10-02: red on both tests.
    - `commit=False`: `True is not false`, because the tags were written at once.
    - The unbound form errored with `RelatedObjectDoesNotExist: Profile has no user`, not the planned `ValueError`. That `ValueError`'s message calls `str(profile)`, which fails first on an unsaved profile. It is the same root cause, fixed by guarding on `instance.pk`.
    - Then green, with `set()` moved into `_save_m2m()`.
- [x] 23. (Findings 5, 7 and 8, plus the security info item on errors) Test hardening. Commit `refactor(profile-page): tighten the profile tests`. Changes:
  - **Atomicity:** a test patches `Tag.objects.get_or_create_by_name` to raise on its second call. Saving `"Python, Rust"` then raises, alice's name is unchanged and no tag was created.
    - Guard mutation: remove the atomic wrapper, which must go red. Revert afterwards.
  - **404 bodies:** the AC5 "no data in the 404 body" checks become a comparison: the foreign-pk response content equals the missing-pk response content, for detail and for edit by GET and POST. The vacuous `assertNotContains` checks go.
  - **AC3 precondition:** the fixture-user test asserts there is no profile before the GET, and exactly one after.
  - **Escaped errors:** a test POSTs `focus_areas="<script>alert(1)</script>\u200b"`, and the error response contains the escaped entry and never the raw `<script>alert(1)</script>`.
  - Done 2026-10-02: all four changes are in, and the suite is green.
    - The atomicity guard went red under the mutation (`'Alice' != ''`, because the name save wasn't rolled back) and was restored.
    - The new escaping test first errored on `self.path`, which isn't defined in `ProfileEscapingTests`. It now uses `reverse("profiles:edit", …)`.
- [ ] 24. (Findings 6 and 9) Docs. No test. Commit `docs(profile-page): correct the tag and ownership notes`.
  - `CLAUDE.md` Tags bullet:
    - `save()` normalises (NFKC, trim, collapse)
    - the 50-character limit and the Cc/Cf and comma checks apply only through `full_clean()`/`clean_name()`
    - rows written before this ticket, or through `update()`/`bulk_create()`, aren't renormalised (no data migration, as there is no production data)
    - profiles take at most 20 focus areas
  - `CLAUDE.md` auth bullet: "scope the queryset to `request.user`, as `profiles.views.OwnProfileMixin` does for profiles".

## Coverage
| AC | Steps |
|---|---|
| AC1 URLs `mine`, `detail`, `edit` | 1, 5, 6 |
| AC2 login required (all three, POST too) | 3, 5, 7 |
| AC3 `/profile/` redirects, creating a missing profile | 5 |
| AC4 detail content, placeholders, Edit link | 1, 2, 6 |
| AC5 others' and missing ids are 404, nothing leaked or changed | 4, 7 |
| AC6 edit form, pre-filled, CSRF | 6, 14 |
| AC7 valid save: trimmed, focus-area parsing, redirect and message | 8, 9, 20, 21, 22 |
| AC8 invalid input: field errors, nothing saved | 10, 12 |
| AC9 tag normalisation: NFKC, whitespace, control characters, validation before lookup | 11, 12, 13 |
| AC10 no other users' data, no tag list | 15 |
| AC11 nav username link | 17 |
| AC12 escaping | 16 |
| AC13 focus-area input bounded | 19 |
