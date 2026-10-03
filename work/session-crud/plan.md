# Plan: session-crud

## Research summary

**Data layer**
- `LearningSession` (`learning_sessions/models.py`) fields:
  - `goal`: FK, CASCADE, `related_name="sessions"`.
  - `date`: `default=timezone.localdate`, validator `reject_future_dates`.
  - `duration_minutes`: 1–1,440, validators plus a `CheckConstraint`.
  - `notes`: `MaxLengthValidator(2000)`.
  - `tags`: M2M to `tags.Tag`, `related_name="sessions"`.
  - `created_at` / `updated_at`.
- Its manager is `LearningSessionQuerySet.owned_by(user)` (`goal__owner=user`). Ordering is `("-date", "-created_at", "-id")`. There is no `get_absolute_url`.
- The app has no forms, views, urls or templates yet, and is not in `config/urls.py`.
- `Tag` (`tags/models.py`):
  - `TagManager.clean_name(name)` validates without touching the DB.
  - `get_or_create_by_name(name)` returns `(tag, created)`, validates first and is race-safe.
  - `Meta.ordering = ("name",)`, which is case-sensitive.
  - There is no shared form code in `tags/`.
- `profiles/forms.py` has the only comma-list parsing:
  - `MAX_FOCUS_AREAS = 20` and `MAX_FOCUS_AREAS_LENGTH = 1000`.
  - `clean_focus_areas`: NFKC normalise, split on `,`, strip, skip empties, `clean_name` each entry, collect errors as `“entry”: message`, dedupe on `casefold()`, then the count check "You can have at most 20 focus areas."
  - `@transaction.atomic save()`, and `_save_m2m()` sets tags via `get_or_create_by_name`.
- Goals (`goals/views.py`):
  - `OwnGoalsMixin(LoginRequiredMixin)` scopes `get_queryset`. The rules are: mixin first, no `model`.
  - `GoalDetailView` is `pass`.
  - `GoalDeleteView` overrides `get_success_message` with a fixed string, because DeleteView's `cleaned_data` is empty.
  - `Goal.get_absolute_url` returns `goals:detail`.
- `config/urls.py` order is admin, `accounts/`, `profile/`, `goals/`, then `""` → core. Namespaces come from each app's `app_name`.
- Django 6.1.1. `DateInput` has no `input_type` kwarg; use `attrs={"type": "date"}` with `format="%Y-%m-%d"`, otherwise a bound or initial date is localised and the browser's date input shows it empty.
- Settings: `TIME_ZONE="UTC"`, `USE_TZ=True`. Messages and CSRF middleware are on.
- There are no templatetags anywhere.

**Templates**
- `base.html` has one `{% block content %}`. Messages are rendered in a `<ul>` above `<main>`.
- Forms are rendered whole with `{{ form }}` and a bare Save button. The Cancel link is a `hover:underline` link.
- List items use `rounded border border-slate-200 bg-white px-4 py-3`. Pagination is `<nav aria-label="Pages">` with Previous/Next built with `{% querystring page=... %}`. Delete links and buttons use `text-red-700`.
- `goal_detail.html` has an actions row (`mt-6 flex gap-6`). `goal_confirm_delete.html` has the paragraph "This can't be undone."

**Tests**
- Django `TestCase`, data in `setUp`, no factories.
- Users are created with `create_user("alice", password=PASSWORD)` plus `force_login`. `PASSWORD = "Tr4ck-Learning!"` is copied per module.
- Helpers `get_page(client, path)` (returns a `PageParser`) and `login_redirect(path)` are copied per module. Use `assertRedirects(..., fetch_redirect_response=False)`.
- Patterns to mirror:
  - Cross-user tests loop over `(page, method)` with `subTest`, compare against a missing pk (`999999`, identical `content`), and check the object is untouched.
  - CSRF tests use `Client(enforce_csrf_checks=True)` and read the token via `page.forms("main")`.
  - Escaping tests use `PAYLOAD = "<script>alert(1)</script>"` with `assertNotContains` and `assertContains` of the escaped form.
  - Pagination tests use 21 objects plus another user's 30, `("?page=2", "Next") in page.links("main")`, and `?page=99` gives 404.
  - Messages are checked by following the redirect and using `assertContains`.
  - Invalid-input tables use `assertFormError`.
  - The clock is frozen with `patch("django.utils.timezone.now", return_value=NOW)`.
  - The atomic-rollback test patches `TagManager.get_or_create_by_name` to raise on the second call (`profiles/tests/test_forms.py:126-149`).
- `PageParser.forms()` collects only `<input>`. Use `page.elements` for textarea, select and attributes.
- `assertNumQueries` is not used yet.
- Run one module: `./.venv/bin/python src/manage.py test learning_sessions.tests.test_views --verbosity 2`. Lint: `./.venv/bin/ruff check .`. Ruff defaults apply (RUF012: class-level options are tuples).

## Design decisions

- **URLs.** New `learning_sessions/urls.py`, `app_name = "learning_sessions"`, mounted with `path("", include("learning_sessions.urls"))` before the core include. Routes:
  - `goals/<int:goal_pk>/sessions/` → `list`
  - `goals/<int:goal_pk>/sessions/new/` → `create`
  - `sessions/<int:pk>/edit/` → `edit`
  - `sessions/<int:pk>/delete/` → `delete`

  The goal routes stay untouched (no `GoalViewsScopingTests` change). There is no conflict with `goals/<int:pk>/...`.
- **Two mixins** in `learning_sessions/views.py`, following the `OwnGoalsMixin` rules (listed first in a view's bases, never `model`):
  - `OwnSessionsMixin(LoginRequiredMixin)`: `get_queryset()` returns `LearningSession.objects.owned_by(request.user)`.
  - `GoalSessionsMixin(OwnSessionsMixin)`, for the collection routes: overrides `dispatch` so that, after the login check, it resolves `self.goal = get_object_or_404(Goal.objects.owned_by(request.user), pk=goal_pk)` before any form handling (AC2). Its `get_queryset()` narrows to `filter(goal=self.goal)`.
  - Rationale: the 404 happens before validation, so another user's goal or session never yields a page of form errors. Member views get their 404 from the scoped `get_object()`, which UpdateView and DeleteView call first in `get()`/`post()`.
- **Views:**
  - `SessionListView(GoalSessionsMixin, ListView)`, `paginate_by = 20`.
  - `SessionCreateView(GoalSessionsMixin, SuccessMessageMixin, CreateView)`: `get_form_kwargs` passes `instance=LearningSession(goal=self.goal)`, so the goal never comes from the request (AC13).
  - `SessionUpdateView(OwnSessionsMixin, SuccessMessageMixin, UpdateView)`.
  - `SessionDeleteView(OwnSessionsMixin, SuccessMessageMixin, DeleteView)`, with a fixed `get_success_message`, like `GoalDeleteView`.
  - All views set an explicit `template_name`. Success URL is `self.object.goal.get_absolute_url()`. Member querysets add `select_related("goal")`.
- **Shared tag field.** Extract the profile parsing into `tags/forms.py`:
  - `TagListField(forms.CharField)`, with parameters `max_tags` and `noun` (used in "You can have at most {max_tags} {noun}."). Its `clean()` returns a list of names. `ProfileForm` uses it with `noun="focus areas"`, so its messages stay unchanged, and `LearningSessionForm` uses `noun="tags"`.
  - `tags_as_text(tags)` builds the comma-joined initial value.
  - Rationale: the 20 / 1,000 caps, the `clean_name` before any lookup, and the error format are already proven in one place. A copy would drift.
- **`LearningSessionForm(ModelForm)`** in `learning_sessions/forms.py`:
  - Explicit `fields = ("date", "duration_minutes", "notes")` plus `tags = TagListField(...)`.
  - `widgets = {"date": DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}`.
  - `@transaction.atomic save()`, and `_save_m2m()` sets tags via `Tag.objects.get_or_create_by_name` (the profile pattern).
  - The edit initial is `tags_as_text(instance.tags.order_by(Lower("name")))`.
  - The date's default comes from the model's callable default (`timezone.localdate`), evaluated each time the form renders. No `initial=` is computed at import.
- **Tag order.** Tags are shown in alphabetical order ignoring case, via a new `LearningSessionQuerySet.with_tags()` that prefetches `Prefetch("tags", queryset=Tag.objects.order_by(Lower("name"), "id"))`. It is used by the list and the goal detail section. Rationale: `Tag.Meta.ordering` is case-sensitive ("Zebra" before "apple"), and the prefetch is also the N+1 fix.
- **Duration display.** A `duration` template filter in `learning_sessions/templatetags/session_format.py`: `45` → "45 min", `120` → "2 h", `90` → "1 h 30 min", `0`/`None` → "0 min". It is used for each session and for totals. Dates display as `|date:"j M Y"`.
- **Shared item markup.** `templates/learning_sessions/_session_item.html` renders one session (date, duration, tags, notes with `linebreaksbr`, Edit and Delete links). It is included by the list page and the goal detail section, so AC5 and AC8 show the same details.
- **Goal pages.** These stay in `goals/views.py`. Sessions are looked up only through `LearningSession.objects.owned_by(request.user).filter(goal=self.object)`, per CLAUDE.md.
  - `GoalDetailView.get_context_data` adds `recent_sessions` (`with_tags()[:5]`) and `total_minutes` (one `Sum("duration_minutes")` aggregate, `or 0`).
  - `GoalDeleteView.get_context_data` adds `session_count`. Neither overrides `get_queryset`, so `GoalViewsScopingTests` still holds.
- **Messages:** "Session added.", "Session updated.", "Session deleted.". All three redirect to the goal detail page, and no `next` parameter is followed.
- **TDD granularity.** Django delivers some ACs as soon as a view exists: CSRF, escaping, model validators through ModelForm, and the callable date default. Their tests go into the step that introduces the page, so every step still starts red on its main behaviour. No separate step is planned that would pass on arrival. The scoping test is introduced with the first route, and each later route step adds its name to the expected set deliberately.

## Steps

- [x] 1. **Refactor: extract `TagListField` and `tags_as_text` into `tags/forms.py`, and switch `ProfileForm` to them.** Profile messages and behaviour stay unchanged. Also generalise the `reject_commas` docstring ("separator for typed tag lists"). No new test; this is a pure refactor (`refactor(session-crud): ...`) that must keep `profiles.tests` and the full suite green. — test: existing `profiles/tests/test_forms.py`, `profiles/tests/test_views.py` — impl: `tags/forms.py` (new), `profiles/forms.py`, `tags/models.py` — covers: groundwork for AC16, AC17
- [x] 2. **Create page, plus access and the scoping guard.** For the owner, GET `/goals/<goal_pk>/sessions/new/` shows a form with:
  - `date` (`type="date"`, value today in `YYYY-MM-DD`)
  - `duration_minutes`
  - `notes` (textarea)
  - `tags` (text)
  - no `goal`, `created_at` or `updated_at` inputs
  - the goal's title and a Cancel link to the goal

  Tests in the same step:
  - The default date is evaluated per request in `TIME_ZONE`, checked with `override_settings(TIME_ZONE="Pacific/Auckland")` and `timezone.now` patched to `2026-03-10 23:30 UTC`, which expects `2026-03-11`.
  - Anonymous GET and POST redirect to login (`next` kept) and store nothing.
  - Another user's goal and a missing goal pk give identical 404s for GET, a valid POST and an invalid POST, and nothing is stored.
  - The goal title is escaped.
  - `SessionViewsScopingTests` walks `learning_sessions.urls` with the expected set `{"create"}`. For each view: `model is None`; `OwnSessionsMixin` comes before Single/MultipleObjectMixin in the MRO; `get_queryset` is the mixin's (or a `GoalSessionsMixin` override); and after `setup()` with alice's ids, the queryset or goal lookup excludes bob's and a lookup of bob's goal raises `Http404`.

  — test: `learning_sessions/tests/test_views.py` (`SessionCreatePageTests`, `SessionCreateAccessTests`, `SessionViewsScopingTests`) — impl: `learning_sessions/urls.py`, `learning_sessions/views.py` (both mixins, `SessionCreateView`), `learning_sessions/forms.py` (`LearningSessionForm`, no tag saving yet), `config/urls.py`, `templates/learning_sessions/session_form.html` — covers: AC1, AC2, AC4, AC11, AC12, AC27
- [x] 3. **Create POST: valid, invalid and boundary values.**
  - A valid POST creates the session on the URL's goal, redirects to the goal detail page, and the followed page shows "Session added.". Posted `goal` (another goal of alice's, and one of bob's), `created_at` and `updated_at` are ignored.
  - A table of invalid input each gives 200, an `assertFormError`, and nothing created: future date, `0`, `1441`, `1.5`, `abc`, empty duration, notes of 2,001 characters.
  - Boundary values save: today, `1`, `1440`, and date plus duration only.
  - CSRF: 403 without a token, 302 with the form's token.

  — test: `learning_sessions/tests/test_views.py` (`SessionCreateTests`, `SessionCreateCsrfTests`) — impl: `learning_sessions/views.py` (`get_form_kwargs` instance with goal, `get_success_url`, `success_message`) — covers: AC13, AC14, AC15, AC26
- [x] 4. **Tags on create.** Tests through the view:
  - `" python , Machine Learning,, MACHINE learning , "` saves the tags `["Machine Learning", "Python"]`, reusing an existing `Python` tag with its own spelling, and creates one "machine learning" tag.
  - An invalid entry (51 characters, or a zero-width space) gives 200 with `“entry”: message` naming it, and no session or tag is created.
  - 21 entries gives "You can have at most 20 tags."; `"x" * 1001` gives the max-length error; exactly 20 entries saves.
  - `get_or_create_by_name` is the creation path: a spy on `TagManager.get_or_create_by_name` sees each name, and no tag exists before the valid save.

  — test: `learning_sessions/tests/test_views.py` (`SessionTagsTests`) — impl: `learning_sessions/forms.py` (`_save_m2m`) — covers: AC16, AC17, AC18
- [x] 5. **Atomic create.** With `TagManager.get_or_create_by_name` patched to raise on the second name, a create POST raises, no session exists, and the first name's new tag is rolled back. — test: `learning_sessions/tests/test_forms.py` (`LearningSessionFormAtomicTests`, form-level like `ProfileFormTests`) — impl: `learning_sessions/forms.py` (`@transaction.atomic save`) — covers: AC19
- [ ] 6. **Edit page and access.**
  - For the owner, GET `/sessions/<pk>/edit/` is pre-filled. The date value is in `YYYY-MM-DD` form, notes are in the textarea, and the tags field reads `"apple, Django, zebra"` (alphabetical ignoring case). The page shows the goal title and a Cancel link to the goal.
  - Anonymous GET and POST redirect to login and change nothing.
  - Another user's session and a missing pk give identical 404s for GET, a valid POST and an invalid POST, and the session is untouched.
  - Notes, tag names and the goal title are escaped.
  - Scoping set becomes `{"create", "edit"}`.

  — test: `learning_sessions/tests/test_views.py` (`SessionEditPageTests`, `SessionEditAccessTests`, scoping set) — impl: `learning_sessions/views.py` (`SessionUpdateView`, `OwnSessionsMixin.get_queryset` with `select_related("goal")`), `learning_sessions/forms.py` (`__init__` tag initial), `learning_sessions/urls.py`, `session_form.html` (edit heading and action) — covers: AC1, AC3, AC4, AC20, AC27
- [ ] 7. **Edit POST.**
  - A valid POST updates the fields, replaces the tags, redirects to the goal and shows "Session updated.".
  - An empty tags field clears all tags.
  - A posted `goal` (alice's other goal or bob's) leaves the goal unchanged.
  - An invalid POST (future date) changes nothing, tags included.
  - Atomic: with the tag step failing, the session keeps its previous values and tags.
  - Shared tags: alice replacing her `python` tag leaves bob's session tagged `python`, and the `Tag` row still exists.
  - CSRF: 403 without a token, 302 with it.

  — test: `learning_sessions/tests/test_views.py` (`SessionEditTests`, `SessionEditCsrfTests`), `learning_sessions/tests/test_forms.py` (edit rollback) — impl: `learning_sessions/views.py` (`SessionUpdateView` success URL and message) — covers: AC19, AC21, AC24, AC26
- [ ] 8. **Delete.**
  - GET `/sessions/<pk>/delete/` shows the session's date, duration and goal title, a POST form to itself, and a Cancel link to the goal. It deletes nothing.
  - POST deletes the session, redirects to the goal and shows "Session deleted.". The goal still exists, the tags still exist, and bob's session with the same tag keeps it.
  - Anonymous and cross-user/missing requests: login redirect or identical 404 for GET and POST, and nothing deleted.
  - CSRF: 403 without a token. The goal title and duration are escaped.
  - Scoping set becomes `{"create", "edit", "delete"}`.

  — test: `learning_sessions/tests/test_views.py` (`SessionDeleteTests`, `SessionDeleteAccessTests`, `SessionDeleteCsrfTests`) — impl: `learning_sessions/views.py` (`SessionDeleteView`), `learning_sessions/urls.py`, `templates/learning_sessions/session_confirm_delete.html`, `learning_sessions/templatetags/session_format.py` (`duration` filter, first use) — covers: AC1, AC3, AC4, AC22, AC23, AC24, AC26, AC27
- [ ] 9. **List page.** GET `/goals/<goal_pk>/sessions/`:
  - Shows the goal title, a link back to the goal, an "Add session" link, and only that goal's sessions (not alice's other goal's, not bob's), newest first by date and then creation.
  - Each item shows the date, the duration formatted as "45 min", "2 h" or "1 h 30 min", tags in alphabetical order ignoring case, notes, and Edit and Delete links to the right URLs.
  - A goal with no sessions shows the empty state.
  - 20 per page, `("?page=2", "Next")` / `"Previous"` links, and `?page=99` and `?page=abc` are both 404.
  - Anonymous GET redirects to login, and another user's or a missing goal gives an identical 404.
  - Notes and tags are escaped.
  - Scoping set becomes `{"list", "create", "edit", "delete"}`.
  - No N+1: the query count with 1 session and 1 tag equals the count with 20 sessions of 3 tags each (`CaptureQueriesContext`). The number is then pinned with `assertNumQueries`. The case-insensitive tag order already requires the `with_tags()` prefetch, so this test belongs here, not in a separate step that would pass on arrival.

  — test: `learning_sessions/tests/test_views.py` (`SessionListTests`, `SessionListPaginationTests`, `SessionListAccessTests`, `SessionListQueryCountTests`, scoping set) — impl: `learning_sessions/views.py` (`SessionListView`, `get_queryset` with `with_tags()`), `learning_sessions/urls.py`, `learning_sessions/models.py` (`with_tags()`), `templates/learning_sessions/session_list.html`, `templates/learning_sessions/_session_item.html` — covers: AC1, AC2, AC4, AC5 (item details), AC8, AC9, AC10, AC27
- [ ] 10. **Goal detail "Sessions" section.**
  - The goal page shows that goal's 5 most recent sessions (from 6 or more; the oldest is absent, other goals' sessions are absent) with the `_session_item.html` details.
  - It shows the total of *all* the goal's sessions, e.g. 6 sessions of 15 min gives "1 h 30 min".
  - "Add session" links to `learning_sessions:create`, and "All sessions" links to `learning_sessions:list`.
  - A goal without sessions shows the empty-state text and a total of "0 min".
  - Notes and tags in the section are escaped.
  - No N+1: the query count is the same for 1 session with 1 tag and for 6 sessions with 3 tags each, pinned with `assertNumQueries` (`with_tags()` prefetch and one `Sum()` aggregate).

  — test: `goals/tests/test_views.py` (`GoalDetailSessionsTests`, `GoalDetailQueryCountTests`) — impl: `goals/views.py` (`GoalDetailView.get_context_data`), `templates/goals/goal_detail.html` — covers: AC5, AC6, AC7, AC10, AC27
- [ ] 11. **Goal delete warning.**
  - With 3 sessions, the goal's delete page says "Its 3 sessions will be deleted too.". With 1: "Its 1 session will be deleted too.".
  - With none: no warning.
  - Another goal's sessions (alice's other goal, bob's) aren't counted.
  - The goal title is still escaped.

  — test: `goals/tests/test_views.py` (`GoalDeleteSessionWarningTests`) — impl: `goals/views.py` (`GoalDeleteView.get_context_data`), `templates/goals/goal_confirm_delete.html` — covers: AC25, AC27
- [ ] 12. **Docs.** Update `CLAUDE.md`:
  - the learning-sessions stack line: routes, mixins, form, `TagListField`, `with_tags()`, the `duration` filter
  - the goal detail section and delete warning
  - the tags line: `TagListField` as the shared typed-tags path
  - the Layout entries for `learning_sessions/`, `tags/` and `templates/`

  `README.md` too if it lists pages. Docs only; the suite stays green (`docs(session-crud): ...`). — test: full suite and `ruff check .` — impl: `CLAUDE.md`, `README.md` — covers: AC28

## AC coverage

| AC | Steps |
|----|-------|
| AC1 anonymous | 2, 6, 8, 9 |
| AC2 foreign or missing goal 404 before form handling | 2, 9 |
| AC3 foreign or missing session 404 before form handling | 6, 8 |
| AC4 scoping test | 2, 6, 8, 9 |
| AC5 detail: 5 recent with details | 9 (item markup), 10 |
| AC6 total of all and links | 10 |
| AC7 empty state, zero total | 10 |
| AC8 list page | 9 |
| AC9 pagination, `?page=abc` | 9 |
| AC10 no N+1 | 9, 10 |
| AC11 field allow-list | 2 |
| AC12 date input and per-request today | 2 |
| AC13 create and ignored fields | 3 |
| AC14 invalid input rejected | 3 |
| AC15 boundaries accepted | 3 |
| AC16 tag parsing and reuse | 1, 4 |
| AC17 invalid tags and caps | 1, 4 |
| AC18 `get_or_create_by_name` only, on save | 4 |
| AC19 atomic | 5, 7 |
| AC20 edit prefill | 6 |
| AC21 edit save, clear tags, goal fixed | 7 |
| AC22 delete confirmation | 8 |
| AC23 delete POST | 8 |
| AC24 shared tags intact | 7, 8 |
| AC25 goal delete warning | 11 |
| AC26 CSRF | 3, 7, 8 |
| AC27 escaping | 2, 6, 8, 9, 10, 11 |
| AC28 CLAUDE.md | 12 |
