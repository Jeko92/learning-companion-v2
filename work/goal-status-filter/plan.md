# Plan: goal-status-filter

## Research summary
- **Project (#7–#9):**
  - `GoalListView(OwnGoalsMixin, ListView)` with `paginate_by = 20` and `goals/goal_list.html`.
  - `OwnGoalsMixin.get_queryset()` returns `Goal.objects.owned_by(request.user)`, and the mixin has no `model`.
  - `Goal.Status.values` is `["planned", "in-progress", "done"]`, with labels Planned / In progress / Done.
  - The list template has an empty state "No goals yet.", and Previous/Next links built as bare `?page=N`. #8's `GoalListPaginationTests` expects `("?page=2", "Next")` and `("?page=1", "Previous")`.
  - `goals/urls.py` routes `list`, `create`, `detail`, `edit` and `delete`.
- **Tests:**
  - Each new behaviour gets an assertion-red. Guards name a mutation, run with `PYTHONDONTWRITEBYTECODE=1`, then revert.
  - Escaping is checked on raw responses.
  - Stage only when the suite and lint both exit 0.
- **Django 6.1.1 (verified by probe):**
  - **`{% querystring %}`:**
    - It is built in (no `{% load %}`), and needs `context.request`, which view rendering provides.
    - With GET `status=done&page=1`, `{% querystring page=2 %}` renders `?status=done&amp;page=2`, and `page=None` removes the key. The output always starts with `?`.
    - An extra `x=<script>…` is percent-encoded and then HTML-escaped, so no raw `<script>` appears.
    - `PageParser` unescapes `&amp;`, so `links()` sees `?status=done&page=2`. On an unfiltered list it gives `?page=2`, so #8's tests still hold.
  - **URLconf walk:** `View.as_view()` sets `callback.view_class`, so `goals.urls.urlpatterns` yields `(p.name, p.callback.view_class)`.
  - **MRO check:** `V(OwnGoalsMixin, ListView).get_queryset is OwnGoalsMixin.get_queryset` is True, while the reverse order gives False. `ListView.model` is None (from `MultipleObjectMixin`), so `cls.model is None` detects a view that sets `model`.
  - **Parsing:** stdlib `HTMLParser` gives `{"aria-current": "page"}`.

## Design decisions
- **Filtering in `GoalListView`:**
  - `get_queryset()` starts from `super().get_queryset()` (the owner-scoped queryset), and filters by `status` only when `request.GET["status"]` is in `Goal.Status.values`. Anything else means no filter.
  - The validated status is exposed as `active_status` in the context (`""` for All).
- **Filter links in `goal_list.html`**, a `<nav aria-label="Filter by status">` in `<main>`:
  - "All" links to `{% url 'goals:list' %}`, and each status links to `{% url 'goals:list' %}?status=<value>`, built from `Goal.Status.choices` passed in the context as `statuses`.
  - The active entry is a `<span aria-current="page">`, not a link.
  - The filter links carry no `page`, so a new filter starts at page 1.
- **Pagination links** use `{% querystring page=page_obj.next_page_number %}` / `previous_page_number`. They keep `status` and any other parameter, safely escaped.
- **Empty states:**
  - The context gives `has_goals` (`OwnGoalsMixin`'s queryset `.exists()`, before filtering).
  - The template shows "No goals with this status." when filtered and `has_goals`, otherwise "No goals yet.".
- **AC8's scoping test** goes in `test_views.py`. It loops over `goals.urls.urlpatterns`, skipping `create`. For each view class it asserts `cls.model is None` and `cls.get_queryset is OwnGoalsMixin.get_queryset`.

## Steps
The user approved this plan on 2026-10-02.

Each step is one red–green–refactor cycle and one commit, `feat(goal-status-filter): …`. The tests go in a new `GoalStatusFilterTests` class in `src/goals/tests/test_views.py`: alice has goals in all three statuses, and bob has goals in the same statuses. Guard steps (3, 7, 8) name their mutation.

- [x] 1. `?status=<value>` filters the list. With subtests for `planned`, `in-progress` and `done`, `GET /goals/?status=<value>` lists exactly alice's goals with that status (titles in `main`, newest first), and none of her others. Expected red: all of her goals are listed. Impl: `GoalListView.get_queryset()` filters `super().get_queryset()` by a valid `status`. Covers: AC1.
- [x] 2. A missing, empty or invalid status shows all goals. With subtests for `/goals/`, `?status=` and `?status=bogus`: 200, and all of alice's goals are listed. Expected red: `?status=bogus` lists none. A naive filter applies any value, so the step 1 implementation stays minimal and step 2 adds the `in Goal.Status.values` check. Impl: validate against `Goal.Status.values`. Covers: AC2.
- [x] 3. The filter stays scoped to the owner. Bob's goals in the same statuses never appear in alice's `?status=<value>` lists. Impl: none, because the filter starts from `super().get_queryset()`. Covers: AC3.
  - Guard. Mutation: filter `Goal.objects.filter(status=…)` instead of `super().get_queryset()`. It must go red (bob's titles appear). Revert afterwards.
  - Done 2026-10-02: green on arrival. Under the mutation, all three subtests went red (bob's titles appeared). The view was then restored.
- [x] 4. The filter links, with the active one marked. Test:
  - On `/goals/`, the `<main>` links include `("/goals/?status=planned", "Planned")`, `("/goals/?status=in-progress", "In progress")` and `("/goals/?status=done", "Done")`. "All" isn't a link, and it's a `span` with `aria-current="page"`.
  - On `?status=done`, `("/goals/", "All")` is a link, and "Done" is the `aria-current="page"` span.
  - On `?status=bogus`, "All" is the active filter.

  Expected red: the filter links are missing. Impl: `active_status` and `statuses` in `get_context_data()`, and the filter nav in `goal_list.html`. Covers: AC4.
- [x] 5. Pagination keeps the filter. Alice has 21 `done` goals, `created_at` set via `update` (oldest `d01` to newest `d21`), plus some goals of other statuses.
  - Page 1 of `?status=done` lists `d21`…`d02`, with a "Next" link to `?status=done&page=2`.
  - Page 2 lists only `d01`, with a "Previous" link to `?status=done&page=1`.
  - The filter links on page 2 contain no `page`.
  - #8's `GoalListPaginationTests` stays green.

  Expected red: the Next link is `?page=2`. Impl: `{% querystring page=… %}` in the pagination links. Covers: AC5.
- [x] 6. The two empty states.
  - Alice has only `planned` goals: `?status=done` shows "No goals with this status." and not "No goals yet.".
  - Carol has no goals: `/goals/` and `?status=done` both show "No goals yet.".

  Expected red: "No goals with this status." is missing. Impl: `has_goals` in the context, and the template's two-way empty state. Covers: AC6.
- [x] 7. Query parameters are never reflected as raw markup. With 21 goals (so pagination links render), `GET /goals/?status=done&x=<script>alert(1)</script>` returns 200, and the response doesn't contain `<script>alert(1)</script>`. Impl: none, because `querystring` percent-encodes and escapes. Covers: AC7.
  - Guard. Mutation: the Next link built as `href="?{{ request.META.QUERY_STRING|safe }}&page=…"`, which with an unencoded test query would reflect raw. It must go red. If the test client sends the query percent-encoded, use `{{ request.GET.x|safe }}` in the link instead, noted in the step. Revert afterwards.
  - Done 2026-10-02: green on arrival. The test client percent-encodes the query, so the mutation used `{{ request.GET.x|safe }}` (as a `data-x` attribute on the Next link). It went red (the raw payload was reflected). The template was then restored.
- [ ] 8. Every goal view is pinned to `OwnGoalsMixin`. A test walks `goals.urls.urlpatterns`; for every route except `create`, `view_class.model is None` and `view_class.get_queryset is OwnGoalsMixin.get_queryset`, with a subtest per route name. It also asserts the walked names are exactly `{"list", "detail", "edit", "delete"}`, so a new route can't slip past the check unnoticed. Impl: none. Covers: AC8.
  - Guard. Mutation: `model = Goal` on `GoalDetailView`. It must go red. Revert afterwards. Then reorder its bases to `(DetailView, OwnGoalsMixin)`, which must go red too.
- [ ] 9. Docs. No test. Commit `docs(goal-status-filter): document the status filter`.
  - `CLAUDE.md` Goals bullet:
    - `/goals/?status=<planned|in-progress|done>` filters the list (invalid values show all)
    - pagination uses `{% querystring %}` so it keeps the filter
    - a test walks every goal view to pin `OwnGoalsMixin`
  - `README.md`: the goal-list sentence mentions the filter.
  - Manual check against `runserver` with curl as alice:
    - `?status=done` lists only her done goal
    - `?status=bogus` lists all
    - the active filter is marked

## Coverage
| AC | Steps |
|---|---|
| AC1 `?status=` filters by planned, in-progress or done | 1 |
| AC2 missing, empty or invalid status shows all | 2 |
| AC3 filter scoped to the owner | 3 |
| AC4 filter links, active marked with `aria-current`, All active by default | 4 |
| AC5 pagination keeps the filter; filter links start at page 1 | 5 |
| AC6 two empty states | 6 |
| AC7 no raw reflection of query parameters | 7 |
| AC8 every goal view pinned to `OwnGoalsMixin` | 8 |
