# Plan: resource-attach

## Research summary

- **Resource model** (`resources/models.py`, from #13): `goal` FK (`goal.resources`, CASCADE), `url` (`HttpURLField`, 2,048, http/https only), `title` (200), `type` (`Resource.Type`: article/video/repo/doc, labels "Article"…, default article), timestamps. `save()`/`clean_fields()` trim `url` and `title`. Constraints: URL scheme check, type check, `UniqueConstraint(goal, url)` with `violation_error_message="This goal already has this resource."`. `ResourceQuerySet.owned_by(user)` filters `goal__owner`. Ordering `-created_at`, `-id`. No views, URLs, forms or templates yet; the app is installed but not in `config/urls.py`.
- **Form behaviour (Django 6.1 source):** `HttpURLField` doesn't override `formfield()`, so the form field is a plain `forms.URLField` (strips whitespace, `assume_scheme="https"`, default `URLValidator` that also allows ftp). The model's http/https validator runs in `_post_clean`, so `ftp:` gets one error (from the model), `javascript:`/`data:` one error (from the form field; the model check is then skipped for that field). `HTTPS://` uppercase and a 2,048-character URL pass. A scheme-less `example.com` is saved as `https://example.com`. The ModelForm excludes `goal`, so `full_clean()` skips the `(goal, url)` unique constraint (comment in the model, `CLAUDE.md`).
- **Pattern to copy** (`learning_sessions/views.py`): `OwnSessionsMixin(LoginRequiredMixin)` (`get_queryset()` = `owned_by(request.user).select_related("goal")`, `get_success_url()` = the goal's page) and `GoalSessionsMixin(OwnSessionsMixin)` (looks the goal up through `Goal.objects.owned_by` in `dispatch` only when authenticated, `get_goal()`, filters the queryset by goal, adds `goal` to the context). `SessionCreateView(GoalSessionsMixin, SuccessMessageMixin, CreateView)` passes `instance=LearningSession(goal=self.goal)` in `get_form_kwargs`. `SessionDeleteView(OwnSessionsMixin, SuccessMessageMixin, DeleteView)` overrides `get_success_message` with fixed text. URLs: `app_name`, shallow nesting, included at `""` in `config/urls.py` before `core.urls`.
- **Templates:** `goals/goal_detail.html` has `<section class="mt-10">` blocks with `<h2 class="text-lg font-semibold">`, cards `rounded border border-slate-200 bg-white px-4 py-3`, Delete links `font-medium text-red-700 hover:underline`. `session_form.html` renders `{{ form }}`, a Save button and a Cancel link; `session_confirm_delete.html` is h1, summary, "This can't be undone.", a POST form with `{% csrf_token %}` and a Cancel link. `goal_confirm_delete.html` shows `Its N session{{ n|pluralize }} will be deleted too.` in `text-red-700`. `base.html` renders messages.
- **Goal views:** `GoalDetailView.get_context_data` adds `recent_sessions` and `total_minutes` via `LearningSession.objects.owned_by(...)`; `GoalDeleteView` adds `session_count`. `GoalDetailQueryCountTests` (`goals/tests/test_views.py:863`) pins `assertNumQueries(6)` ("Login session, user, goal, total, recent sessions, their tags") and compares a large and a small goal with `CaptureQueriesContext`. `GoalDeleteSessionWarningTests` checks the warning text in `page.text("main")`.
- **Test conventions:** `django.test.TestCase`; per-module `PASSWORD`, `PAYLOAD`/`ESCAPED`, `get_page()` (`PageParser`), `login_redirect()`, `valid_data(**changes)`; users via `create_user`, login via `force_login`; hard-coded paths plus one `reverse()` check. 404-before-form-handling: as bob, for get / valid post / invalid post, compare status and content with a missing pk and assert nothing stored. CSRF: `Client(enforce_csrf_checks=True)`, POST without token is 403, POST with the page's token is 302. Escaping: `assertNotContains(PAYLOAD)` + `assertContains(ESCAPED)`. Messages via following the redirect. Scoping tests find routes by namespace through `get_resolver()` and check `model is None`, mixin before `SingleObjectMixin`/`MultipleObjectMixin` in the MRO, inherited `get_queryset`, and the `get_goal()` 404 via `RequestFactory`. `PageParser.forms()` collects `<input>` only; `<select>` is checked through `page.elements`. No shared factories; `resources/tests/test_models.py` has `build_resource`/`make_resource`. Run one module: `./.venv/bin/python src/manage.py test resources.tests.test_views --verbosity 2`.

## Design decisions

- **Mirror the sessions views.** `resources/views.py` gets `OwnResourcesMixin(LoginRequiredMixin)` and `GoalResourcesMixin(OwnResourcesMixin)`, with the same rules (listed first, no `model`), and `ResourceCreateView` / `ResourceDeleteView`. Rationale: one proven scoping pattern, and `ResourceViewsScopingTests` can mirror `SessionViewsScopingTests`.
- **Duplicates are checked in the form.** `ResourceForm.validate_constraints()` also validates the `(goal, url)` constraint (in Django 6.1 a `UniqueConstraint` is checked there, not in `validate_unique()`; corrected during step 4), using the goal the view sets on the instance, so the error is the model's own message, reported as a non-field error. Rationale: one message, one source, and `form.is_valid()` stays honest without view code.
- **The race is handled in the view.** `ResourceCreateView.form_valid` saves inside `transaction.atomic()`. On `IntegrityError` it checks whether the goal now has that URL: if so, it adds the same non-field error (no duplicated literal) and returns `form_invalid`; otherwise it re-raises, so unrelated integrity errors are not masked.
- **The URL form field stays Django's default.** The model validator already limits schemes to http/https with one error. The `assume_scheme="https"` behaviour (`example.com` saved as `https://example.com`) is kept and pinned by a test, so a Django change shows up.
- **Grouping lives on the queryset.** `ResourceQuerySet.grouped_by_type()` evaluates the queryset once and returns `[(heading, [resources])]` in `Resource.Type` order, skipping empty types. Headings are "Articles", "Videos", "Repos", "Docs", and a test requires one heading for every `Type` value, so a new type can't be silently dropped. Rationale: one query, and the template stays a plain loop.
- **Inline form plus a standalone page.** The goal page renders an unbound `ResourceForm` (no query: choices are static) posting to `resources:create`. GET and invalid POSTs on the create route render `resources/resource_form.html`, like `session_form.html`.
- **Links** use `href="{{ resource.url }}"` (autoescaped; only http(s) can be stored) with `target="_blank" rel="noopener noreferrer"`.
- **Templates** live in `src/templates/resources/` (`resource_form.html`, `resource_confirm_delete.html`). The goal page section is written inline in `goal_detail.html`; no partial, as nothing else lists resources.
- **Query count:** the goal page gains exactly one query (the resources), so the pin goes from 6 to 7 deliberately, with the comment updated.

## Steps

- [x] 1. **Create page, access and the scoping guard.** New `resources/urls.py` (`app_name = "resources"`, `goals/<int:goal_pk>/resources/new/` named `create`), included at `""` in `config/urls.py`. For the owner, GET shows `resources/resource_form.html`: a POST form whose action is the page itself, with `url` and `title` inputs, a `type` `<select>` with the four types and Article selected, no `goal`/timestamp field, the goal's title (escaped) and a Cancel link to the goal. Tests in the same step:
  - `reverse("resources:create", args=[pk])` is the path
  - anonymous GET and POST redirect to login with `next`, nothing stored
  - bob's goal: get / valid post / invalid post are a 404 identical to a missing goal pk, nothing stored
  - `ResourceViewsScopingTests` (routes by namespace `resources`) expects exactly `{"create"}` and checks `model is None`, `OwnResourcesMixin` before the generic mixins, the inherited `get_queryset`, and that `get_goal()` 404s for bob's goal and scopes the queryset to the goal

  — test: `resources/tests/test_views.py` (`ResourceCreatePageTests`, `ResourceCreateAccessTests`, `ResourceViewsScopingTests`) — impl: `resources/urls.py` (new), `resources/views.py` (new: `OwnResourcesMixin`, `GoalResourcesMixin`, `ResourceCreateView`), `resources/forms.py` (new: `ResourceForm`, fields `url`, `title`, `type`), `templates/resources/resource_form.html` (new), `config/urls.py` — covers: AC1, AC2, AC4, AC10, AC12, AC20

- [x] 2. **Create POST: valid data and CSRF.** A valid POST creates the resource on the goal in the URL with title and URL stored trimmed, redirects to the goal page and shows "Resource added.". POSTed `goal` (another goal's pk), `created_at` and `updated_at` are ignored. A scheme-less `example.com` is stored as `https://example.com`. With `enforce_csrf_checks`, a POST without a token is 403 and stores nothing; with the page's token it is 302.

  — test: `resources/tests/test_views.py` (`ResourceCreateTests`, `ResourceCreateCsrfTests`) — impl: `resources/views.py` (`get_form_kwargs` instance with the goal, `success_message`, mixin `get_success_url`) — covers: AC10, AC11, AC19

- [x] 3. **Create POST: invalid and boundary values.** Each of these re-renders the create page (status 200) with a form error, keeps the entered values, and stores nothing: missing URL, missing title, whitespace-only title, malformed URL, `javascript:`, `data:` and `ftp:` URLs (each exactly one `url` error), a 201-character title, a 2,049-character URL, an unknown type. Accepted: a 200-character title, a 2,048-character URL, `HTTPS://…`, each of the four types. A re-rendered entered title containing `PAYLOAD` is escaped.

  — test: `resources/tests/test_views.py` (`ResourceCreateValidationTests`) — impl: whatever the tests show is missing (expected none beyond step 2; if all pass immediately, the step is a characterisation of the model validators and is committed as tests only, saying so in the commit body) — covers: AC12, AC13, AC14, AC20

- [x] 4. **Duplicate URL on the same goal.** `ResourceForm` with `instance=Resource(goal=goal)` and a URL the goal already has (also with surrounding whitespace) is invalid with the non-field error "This goal already has this resource."; the same URL for another goal (including another user's) is valid. Through the view, the POST re-renders with that error and stores nothing.

  — test: `resources/tests/test_forms.py` (new, `ResourceFormDuplicateTests`), `resources/tests/test_views.py` (`ResourceCreateDuplicateTests`) — impl: `resources/forms.py` (`validate_constraints` covering the `(goal, url)` constraint) — covers: AC15

- [x] 5. **Duplicate that only the database catches.** With `ResourceForm.validate_constraints` patched to a no-op (so a duplicate reaches the insert, as in a race), posting an existing URL returns the create page (200) with "This goal already has this resource.", no 500, and the goal still has one such resource. A different `IntegrityError` (the URL is not a duplicate; `Resource.save` patched to raise) is re-raised, not reported as a duplicate.

  — test: `resources/tests/test_views.py` (`ResourceCreateRaceTests`) — impl: `resources/views.py` (`form_valid`: `transaction.atomic()`, catch `IntegrityError`, re-check, `form.add_error(None, …)`) — covers: AC15

- [x] 6. **Delete page and POST.** New route `resources/<int:pk>/delete/` named `delete`. GET shows `resources/resource_confirm_delete.html`: title, URL and goal title (all escaped), a POST form with a CSRF token, a Cancel link to the goal; deletes nothing. POST deletes, redirects to the goal page and shows "Resource deleted."; the goal and its other resources remain. Anonymous GET/POST redirect to login and delete nothing. Bob's resource: GET and POST are a 404 identical to a missing pk, nothing deleted. CSRF: no token is 403 and deletes nothing; the page's token is 302. `ResourceViewsScopingTests` now expects exactly `{"create", "delete"}`, and the delete view's queryset is `owned_by` (alice's resources on both her goals, never bob's).

  — test: `resources/tests/test_views.py` (`ResourceDeleteTests`, `ResourceDeleteAccessTests`, `ResourceDeleteCsrfTests`, `ResourceViewsScopingTests`) — impl: `resources/urls.py`, `resources/views.py` (`ResourceDeleteView`, fixed `get_success_message`), `templates/resources/resource_confirm_delete.html` (new) — covers: AC1, AC3, AC4, AC16, AC17, AC19, AC20

- [x] 7. **`ResourceQuerySet.grouped_by_type()`.** Returns `[(heading, [resources])]` in the order Articles, Videos, Repos, Docs; types without resources are omitted; resources within a group are newest first; it runs one query; every `Resource.Type` value has a heading.

  — test: `resources/tests/test_models.py` (`ResourceGroupedByTypeTests`) — impl: `resources/models.py` — covers: AC5 (groundwork), AC9 (one query)

- [ ] 8. **Resources section on the goal page.** `GoalDetailView` adds `resource_groups` (`Resource.objects.owned_by(user).filter(goal=…).grouped_by_type()`) and an unbound `resource_form`. The section ("Resources" h2) shows one h3 per non-empty group in the fixed order; each resource's title links to its URL with `target="_blank"` and `rel="noopener noreferrer"`, plus a Delete link to `resources:delete`; other goals' resources never appear; without resources it says "No resources yet.". The inline form posts to `resources:create` with a CSRF token, `url`/`title` inputs and the type select (Article selected). Resource title and URL are escaped. **Deliberate pin change:** `GoalDetailQueryCountTests` gets resources of every type on the large goal (one on the small one), the fixed count goes from 6 to 7 and its comment adds "resources".

  — test: `goals/tests/test_views.py` (`GoalDetailResourcesTests`, `GoalDetailQueryCountTests`) — impl: `goals/views.py`, `templates/goals/goal_detail.html` — covers: AC5, AC6, AC7, AC8, AC9, AC20

- [ ] 9. **Resource count on the goal delete confirmation.** `GoalDeleteView` adds `resource_count` (through `Resource.objects.owned_by`). The page says "Its 1 resource will be deleted too." / "Its 2 resources will be deleted too." next to the sessions warning; no resource warning for a goal without resources; resources of the user's other goal and of bob's goal are not counted.

  — test: `goals/tests/test_views.py` (`GoalDeleteResourceWarningTests`) — impl: `goals/views.py`, `templates/goals/goal_confirm_delete.html` — covers: AC18

- [ ] 10. **Docs.** `CLAUDE.md`: the Resources bullet gets the routes, the two mixins and their rules, `ResourceForm` (allow-list, the duplicate check in `validate_constraints` plus the `IntegrityError` re-check in the view, replacing the "#14's attach form must check" note), `grouped_by_type()`, the goal page section and query count, the goal delete warning and `ResourceViewsScopingTests`; the Layout bullets for `src/resources/` and `src/templates/` add the views, URLs, form and `resources/` templates. No test (docs only).

  — test: none (docs) — impl: `CLAUDE.md` — covers: AC21

## AC coverage

| AC | Steps |
|----|-------|
| AC1 anonymous | 1, 6 |
| AC2 other user's goal 404 before form handling | 1 |
| AC3 other user's resource 404 | 6 |
| AC4 scoping test | 1, 6 |
| AC5 grouped by type | 7, 8 |
| AC6 links, Delete, no other goals | 8 |
| AC7 empty state | 8 |
| AC8 inline form | 8 |
| AC9 fixed query count | 7, 8 |
| AC10 allow-list, ignored fields | 1, 2 |
| AC11 valid create | 2 |
| AC12 standalone page, invalid re-render | 1, 3 |
| AC13 rejected values | 3 |
| AC14 boundary values | 3 |
| AC15 duplicates and race | 4, 5 |
| AC16 delete confirmation | 6 |
| AC17 delete POST | 6 |
| AC18 goal delete warning | 9 |
| AC19 CSRF | 2, 6 |
| AC20 escaping | 1, 3, 6, 8 |
| AC21 docs | 10 |
