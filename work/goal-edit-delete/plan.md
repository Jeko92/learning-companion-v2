# Plan: goal-edit-delete

## Research summary
- **Project (#7, #8):**
  - **`goals/views.py`:**
    - `OwnGoalsMixin(LoginRequiredMixin)` sets `model = Goal`, and its `get_queryset()` returns `Goal.objects.owned_by(request.user)`.
    - `GoalListView(OwnGoalsMixin, ListView)` uses `paginate_by = 20`.
    - `GoalCreateView(LoginRequiredMixin, SuccessMessageMixin, CreateView)` uses `form_class = GoalForm`, `success_url = reverse_lazy("goals:list")` and "Goal created.". Its `form_valid` sets the owner.
  - **`GoalForm`** has `Meta.fields = ("title", "description", "status")`.
  - **Templates:** `goals/goal_list.html` lists titles as plain text, and `goals/goal_form.html` has a hard-coded "New goal" heading and a create `action`.
  - **#8's create test** asserts a redirect to `/goals/`; AC11 changes it deliberately.
- **Tests:**
  - New views get an assertion-red from a literal path with the status asserted first.
  - Guards name a mutation, run with `PYTHONDONTWRITEBYTECODE=1`, then revert.
  - Escaping is checked on raw responses.
  - CSRF uses `Client(enforce_csrf_checks=True)` with a GET first.
  - #6's "identical 404" pattern compares the foreign-pk response content with the missing-pk one.
- **Django 6.1.1 (verified by probe):**
  - **Success URL:** with `success_url` unset, `CreateView` and `UpdateView` redirect to `object.get_absolute_url()`. A set `success_url` wins, so #8's must be removed for AC11.
  - **`DeleteView`:**
    - A GET renders the confirmation and doesn't delete.
    - A POST validates an empty `Form`, then `form_valid` resolves the success URL, deletes and redirects.
    - The default template is `goals/goal_confirm_delete.html`.
    - `SuccessMessageMixin` works when listed first, but `cleaned_data` is `{}`. A `success_message` with `%(title)s` raises `KeyError` **after** the row is deleted, so override `get_success_message()` instead (`self.object` is still readable).
  - **Mixin order:** with the mixin listed *after* the generic view, `SingleObjectMixin` / `MultipleObjectMixin.get_queryset` wins. Once `model` is gone from the mixin, that raises `ImproperlyConfigured: … is missing a QuerySet` for `DetailView`, `UpdateView`, `DeleteView` and `ListView`. With the mixin first, all work. `UpdateView` with only `form_class` never needs `model`.
  - **Admin "View on site":** with `get_absolute_url`, the change page renders `<a href="/admin/r/<ct>/<pk>/" class="viewsitelink">View on site</a>`. The shortcut redirects to `http://<host>/goals/<pk>/` without `django.contrib.sites`.
  - **`linebreaksbr`:** it escapes first, so `"<script>x</script>\nline2"` renders as `&lt;script&gt;x&lt;/script&gt;<br>line2`.
  - **Shared form template:** `goal_form.html` gets `object`/`goal` only on update, so `{% if object %}Edit goal{% else %}New goal{% endif %}` works.

## Design decisions
- **`Goal.get_absolute_url()`** returns `reverse("goals:detail", args=[self.pk])`.
  - Create and edit redirect through it (`success_url` removed from `GoalCreateView`).
  - Templates link with `{{ goal.get_absolute_url }}`.
  - The admin gets "View on site".
- **Views** (`goals/views.py`), each listing `OwnGoalsMixin` **first**:
  - `GoalDetailView(OwnGoalsMixin, DetailView)`
  - `GoalUpdateView(OwnGoalsMixin, SuccessMessageMixin, UpdateView)` with `form_class = GoalForm` and `success_message = "Goal updated."`
  - `GoalDeleteView(OwnGoalsMixin, SuccessMessageMixin, DeleteView)` with `success_url = reverse_lazy("goals:list")`, and `get_success_message()` returning "Goal deleted."
  - All use Django's default template names.
- **`OwnGoalsMixin` drops `model = Goal`,** so a wrongly ordered view raises `ImproperlyConfigured` instead of serving unscoped goals.
- **URLs:** `"<int:pk>/"` is `detail`, `"<int:pk>/edit/"` is `edit`, and `"<int:pk>/delete/"` is `delete`.
- **Templates:**
  - `goal_detail.html`: title, status label, the description through `linebreaksbr` (or "No description."), "Created"/"Updated" dates, and links "Edit goal", "Delete goal" and "Back to goals".
  - `goal_form.html`: shared. Its heading and `action` depend on `object`, and edit gets a "Cancel" link to `object.get_absolute_url`.
  - `goal_confirm_delete.html`: "Delete “{{ object.title }}”?", a POST form with `{% csrf_token %}` and a "Delete" button, and a "Cancel" link.
  - `goal_list.html`: titles become `<a href="{{ goal.get_absolute_url }}">`.

## Steps
The user approved this plan and the acceptance criteria on 2026-10-02.

Each step is one red–green–refactor cycle and one commit, `feat(goal-edit-delete): …`.
- Tests go in `src/goals/tests/test_views.py` (new classes per page) and `test_models.py` (`get_absolute_url`); the admin check goes in `test_admin.py`.
- Guard steps (4, 9, 12, 13, 14) name their mutation, which runs with `PYTHONDONTWRITEBYTECODE=1`.
- Stage only when the suite and lint both exit 0.

- [x] 1. The detail page is served. Alice, logged in, `GET /goals/<pk>/`:
  - status 200, **asserted first**
  - `goals/goal_detail.html` and `base.html` are used
  - `reverse("goals:detail", args=[pk]) == f"/goals/{pk}/"`

  Expected red: `404 != 200`. Impl: the `detail` route, `GoalDetailView(OwnGoalsMixin, DetailView)`, and a minimal template. Covers: AC1 (detail), AC4.
- [ ] 2. `Goal.get_absolute_url()` and the admin's "View on site".
  - In `test_models.py`: assert `hasattr(Goal, "get_absolute_url")` first, then `goal.get_absolute_url() == f"/goals/{goal.pk}/"`.
  - In `test_admin.py`: the superuser's change page for a goal contains an `a.viewsitelink`.

  Expected red: `False is not true`. Impl: `get_absolute_url`. Covers: AC15 (method, admin).
- [ ] 3. The detail page shows the goal. Subtests:
  - **filled:** the title, "In progress", a two-line description rendered with a `<br>` between the lines (a `br` in `page.elements`, both lines in `main`), "Created" and "Updated", and a "Back to goals" link to `/goals/`
  - **empty description:** "No description."

  Expected red: the title is missing from `main`. Impl: the detail template. Covers: AC4.
- [ ] 4. The detail page requires login, and another user's goal is a 404 identical to a missing one. Tests:
  - an anonymous GET redirects to login with `next=/goals/<pk>/`
  - bob GETs alice's goal: 404, and the content equals that of `GET /goals/999999/`

  Impl: none, since `OwnGoalsMixin` covers it. Covers: AC2 (detail), AC3 (detail).
  - Guard. Mutation: `GoalDetailView(LoginRequiredMixin, DetailView)` with `model = Goal` (unscoped). Bob's request must go red (200). Revert afterwards.
- [ ] 5. List titles link to the goal. `links("main")` on `/goals/` includes `(goal.get_absolute_url(), goal.title)` for each goal. Expected red: the link is missing. Impl: `<a href="{{ goal.get_absolute_url }}">` in `goal_list.html`. Covers: AC5, AC15 (templates).
- [ ] 6. Creating a goal now opens it.
  - **Test change:** #8's `test_a_valid_create_saves_your_goal_and_returns_to_the_list` is rewritten deliberately to expect a redirect to `goal.get_absolute_url()`, with "Goal created." on the followed page.
  - **New test:** `test_after_creating_you_land_on_the_goal`.

  Expected red: `'/goals/' != '/goals/<pk>/'`. Impl: remove `success_url` from `GoalCreateView`, so it uses `get_absolute_url`. Covers: AC11, AC15 (redirect).
  - This deliberately changes #8 AC6, recorded in the commit body.
- [ ] 7. The edit page renders the goal in a form, and the detail page links to it. `GET /goals/<pk>/edit/`:
  - status 200, asserted first, with `goals/goal_form.html` used
  - `reverse("goals:edit", …)` matches
  - one POST form whose `action` is the edit URL, a CSRF token, `title` pre-filled, a `description` textarea holding the description, and the `status` option for the goal's status `selected`
  - no `owner`
  - `main` contains "Edit goal" and not "New goal", and a "Cancel" link goes to the detail URL
  - the detail page's `links("main")` includes `(edit URL, "Edit goal")`

  Expected red: `404 != 200`. Impl:
  - the `edit` route
  - `GoalUpdateView(OwnGoalsMixin, UpdateView)` with `form_class = GoalForm`
  - `goal_form.html`'s conditional heading, `action` and Cancel link
  - the detail page's Edit link

  Covers: AC1 (edit), AC4 (link), AC6.
- [ ] 8. A valid edit saves and returns to the goal with a message. POST `title="  Learn Django well "`, `description="All parts"`, `status="done"` and `owner=<bob.pk>`. Assert:
  - a redirect to `goal.get_absolute_url()`
  - the saved values, with the title trimmed
  - the owner is still alice
  - with `follow=True`, "Goal updated." is shown

  Expected red: "Goal updated." is missing (the redirect already works). Impl: `SuccessMessageMixin` and `success_message` on `GoalUpdateView`. Covers: AC7.
- [ ] 9. An invalid edit re-renders the form and leaves the goal unchanged. Subtests mirror #8's create cases: blank and whitespace title, 201-character title, 2,001-character description, bogus status. Each asserts 200, `goal_form.html`, `assertFormError` with the message in `main`, and the goal's values unchanged. Impl: none, since `GoalForm` and the model validators are shared. Covers: AC8.
  - Guard. Mutation: drop `MaxLengthValidator(2000)` from `Goal.description` (no migration needed for the run). The description case must go red. Revert afterwards.
- [ ] 10. Delete asks for confirmation, and the detail page links to it. `GET /goals/<pk>/delete/`:
  - status 200, asserted first, with `goals/goal_confirm_delete.html` used
  - `reverse("goals:delete", …)` matches
  - `main` contains `Delete “<title>”?`
  - one POST form with the delete URL as `action`, a CSRF token, a "Delete" button, and a "Cancel" link to the detail URL
  - after the GET, the goal still exists
  - the detail page links "Delete goal" to the delete URL

  Expected red: `404 != 200`. Impl: the `delete` route, `GoalDeleteView(OwnGoalsMixin, DeleteView)` with `success_url = reverse_lazy("goals:list")`, the template, and the detail page's Delete link. Covers: AC1 (delete), AC4 (link), AC9.
- [ ] 11. Confirming deletes the goal with a message. A POST to the delete URL gives a redirect to `/goals/`, and the goal is gone. With `follow=True`, "Goal deleted." is shown and the title isn't listed. Expected red: "Goal deleted." is missing (the delete already works). Impl: `SuccessMessageMixin` with a `get_success_message()` override, since `%(title)s` would raise `KeyError` after the delete. Covers: AC10.
- [ ] 12. Edit and delete are login-required and owner-scoped. Subtests for edit and delete, each with GET and POST:
  - **anonymous:** redirected to login with `next`, and alice's goal unchanged and not deleted
  - **bob on alice's goal:** 404, with content identical to the same request for pk 999999, and alice's goal unchanged and not deleted

  Impl: none. Covers: AC2 (edit, delete), AC3 (edit, delete).
  - Guard. Mutation: `GoalUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView)` with `model = Goal`. Bob's edit subtests must go red. Revert afterwards. Then the same mutation on `GoalDeleteView`.
- [ ] 13. CSRF is enforced on edit and delete. With `Client(enforce_csrf_checks=True)`, GET the edit page and the delete page first. For each:
  - a POST without a token returns 403, and nothing changes
  - a POST with the token read from that page's form (asserting `len(tokens) == 1`) returns 302

  Impl: none. Covers: AC12.
  - Guard. Mutation: `@method_decorator(csrf_exempt, name="dispatch")` on `GoalUpdateView`. The no-token edit case must go red. Revert afterwards.
- [ ] 14. Goal values are escaped. Alice's goal has a title and description of `<script>alert(1)</script>`. The detail, edit and delete pages must not contain the raw payload, and must contain `&lt;script&gt;alert(1)&lt;/script&gt;`. Impl: none. Covers: AC13.
  - Guard. Mutation: `{{ object.description|safe|linebreaksbr }}`, or `|safe` on the description, in `goal_detail.html`. The detail subtest must go red. Revert afterwards.
- [ ] 15. A wrongly ordered ownership mixin fails loudly. Define a class inside the test, `class WronglyOrdered(DetailView, OwnGoalsMixin)`, then call `WronglyOrdered.as_view()` on a `RequestFactory` GET with `request.user = alice` and `pk=goal.pk`. It must raise `ImproperlyConfigured`. Expected red: no exception, because the mixin still sets `model` and the view serves the goal. Impl: remove `model = Goal` from `OwnGoalsMixin`, which all the correctly ordered views keep working without. Covers: AC14.
- [ ] 16. Docs. No test. Commit `docs(goal-edit-delete): document the goal detail, edit and delete pages`.
  - `CLAUDE.md`, Goals bullet:
    - the detail, edit and delete pages
    - `get_absolute_url` as the success URL
    - every pk-taking goal view lists `OwnGoalsMixin` first; the mixin has no `model`, so a wrong order raises `ImproperlyConfigured`
  - `CLAUDE.md` Layout line.
  - `README.md`: the user-facing goal pages sentence.
  - Manual check against `runserver` with curl and the fictional users:
    - alice opens a goal, edits it and sees "Goal updated."
    - alice's delete confirmation page, then the delete, shows "Goal deleted."
    - bob gets 404 on alice's detail, edit and delete pages
    - restore the sample goal afterwards

## Coverage
| AC | Steps |
|---|---|
| AC1 URLs `detail`, `edit` and `delete` | 1, 7, 10 |
| AC2 login required (all, GET and POST) | 4, 12 |
| AC3 another user's goal is a 404 identical to a missing one, untouched | 4, 12 |
| AC4 detail page content and links | 1, 3, 7, 10 |
| AC5 list titles link to the detail page | 5 |
| AC6 edit form, pre-filled, "Edit goal", Cancel, no owner | 7 |
| AC7 valid edit: trimmed, redirect, message, owner unchanged | 8 |
| AC8 invalid edit: field errors, unchanged | 9 |
| AC9 delete confirmation page; a GET never deletes | 10 |
| AC10 delete: redirect to list, message, gone | 11 |
| AC11 create opens the new goal | 6 |
| AC12 CSRF on edit and delete | 13 |
| AC13 escaping on detail, edit and delete | 14 |
| AC14 wrongly ordered mixin raises `ImproperlyConfigured` | 15 |
| AC15 `get_absolute_url`: redirects, template links, admin "View on site" | 2, 5, 6 |
