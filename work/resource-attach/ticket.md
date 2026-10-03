# Resources: attach to a goal and show by type
Issue: #14 · Branch: feature/resource-attach

## Story
As a logged-in learner, I want to attach reference material (articles, videos, repos, docs) to my own goals from the goal's page, see it grouped by type, and remove what I no longer need, so that everything I learn from for a goal is in one place.

## Acceptance criteria

Routes follow the sessions' shallow nesting, in `resources/urls.py` (namespace `resources`, mounted at the root): `/goals/<goal_pk>/resources/new/` (create) and `/resources/<pk>/delete/` (delete).

**Access and scoping**
- [x] AC1 An anonymous user is redirected to the login page (with `next`) from the create and delete pages, and an anonymous POST to either changes nothing.
- [x] AC2 Attaching a resource to another user's goal is a 404, identical to a missing goal pk. The 404 happens before any form handling, so a POST there (valid or invalid data) stores nothing and returns a 404, never a page of validation errors.
- [x] AC3 Deleting another user's resource is a 404 for GET and POST, identical to a missing resource pk, and deletes nothing.
- [x] AC4 A scoping test walks the resource URL patterns. For every resource view it requires:
  - the goal or resource is looked up through the owner-scoped querysets (`Goal.objects.owned_by` / `Resource.objects.owned_by`)
  - the ownership mixin comes first in the view's bases
  - no `model` attribute is set

  A new resource route has to be added to the test deliberately, as with `SessionViewsScopingTests`.

**Goal detail page**
- [x] AC5 The goal detail page has a "Resources" section. Resources are grouped by type under one heading per type, in the fixed order Articles, Videos, Repos, Docs. Only types that have resources get a heading. Within a group, resources are newest first.
- [x] AC6 Each resource shows its title as a link to its URL (opening in a new tab with `rel="noopener noreferrer"`) and a Delete link. Resources of other goals never appear.
- [x] AC7 A goal without resources shows an empty-state message ("No resources yet.") and the attach form.
- [x] AC8 The Resources section has the attach form inline: URL, title and type (a select with the four types, defaulting to Article), posting to the create route with a CSRF token.
- [x] AC9 The goal detail page runs a fixed number of database queries, whatever the number of resources and types. Resources are fetched in one query. The `assertNumQueries` pin in `GoalDetailQueryCountTests` is updated deliberately, with its comment.

**Attach (create)**
- [x] AC10 The resource form has an explicit field allow-list: `url`, `title`, `type`. There is no goal field and no timestamp field. POSTed `goal`, `created_at` or `updated_at` values are ignored.
- [x] AC11 A valid POST creates the resource on the goal in the URL, with title and URL stored trimmed. It redirects to the goal detail page and shows "Resource added.".
- [x] AC12 A GET to the create page shows a standalone page with the form, the goal's title and a Cancel link back to the goal. An invalid POST re-renders that page (status 200) with the errors and the entered values, and saves nothing.
- [x] AC13 Each of these is rejected with a form error, and nothing is saved:
  - a missing URL or title, or a title of only whitespace
  - a malformed URL
  - a URL with a scheme other than `http`/`https` (`javascript:`, `data:`, `ftp:`), reported as exactly one error
  - a title over 200 characters, a URL over 2,048 characters
  - a type outside the four choices
- [x] AC14 Boundary values are accepted: a title of exactly 200 characters, a URL of exactly 2,048 characters, an uppercase scheme (`HTTPS://...`), and each of the four types.
- [x] AC15 Attaching a URL that the goal already has (compared after trimming) is rejected with the form error "This goal already has this resource." and saves nothing, never a 500. That also holds when the unique constraint fires at insert time, e.g. two identical attaches racing (simulated in a test by an `IntegrityError` on save). The same URL on another goal, including another user's, is accepted.

**Delete**
- [x] AC16 A GET to the delete page shows a confirmation (the resource's title, URL and goal) with a POST form and a Cancel link back to the goal. It deletes nothing.
- [x] AC17 A POST deletes the resource, redirects to the goal detail page and shows "Resource deleted.". The goal and its other resources still exist afterwards.

**Goal delete (goals app)**
- [x] AC18 The goal delete confirmation page says how many resources will be deleted along with the goal (e.g. "Its 2 resources will be deleted too."), next to the existing sessions warning. For a goal without resources it shows no such warning. The count covers only that goal's resources.

**Safety and docs**
- [x] AC19 POSTs to create and delete without a CSRF token are rejected (403) and change nothing.
- [x] AC20 User-entered text (resource title and URL, goal title) is HTML-escaped on the goal detail page, the create page and the delete confirmation.
- [x] AC21 `CLAUDE.md` documents the resource routes, views, form and templates, the duplicate check, and the goal delete warning.

## Out of scope
- Editing a resource (title, URL or type)
- Fetching page titles or previews from the URL automatically
- A separate resource list page or a global resource list across goals
- Moving a resource to another goal
- Resource counts on the goal list
- Using resources in the AI summary (#16)

## Notes
- **Display:** grouped sections per type, chosen over a flat list with badges. Fixed order is the `Resource.Type` order (article, video, repo, doc); empty types are hidden.
- **Removal:** included, with a confirmation page and POST delete, like session delete.
- **Form placement:** inline on the goal detail page, as the handout asks ("a form to attach a resource to a goal from the goal's detail page"). It posts to its own create route, which also renders a standalone page for GET and for invalid submissions, so errors are shown without re-rendering the whole goal page.
- **Duplicates:** the form has no `goal` field, so `full_clean()` skips the `(goal, url)` unique constraint (see `CLAUDE.md` and the comment in `resources/models.py`). The view or form must check for duplicates itself and also turn an `IntegrityError` from that constraint into the same form error.
- **Ownership** is `goal.owner`. Resources are looked up only through `Resource.objects.owned_by(request.user)`, goals through `Goal.objects.owned_by(request.user)`. After create and delete the user is redirected to the goal detail page; no `next` parameter is followed.
- **Links:** stored URLs are always `http(s)` (validator plus database `CheckConstraint`), so they are safe as `href`s. They open in a new tab with `rel="noopener noreferrer"`.
- **Goal delete warning:** the user chose to include the resource count on the goal delete confirmation in this ticket.
- The issue's open questions (grouped vs badges, removal) were answered in the interview on 2026-10-03.
- **Approval:** the user approved the acceptance criteria (AC1–AC21) on 2026-10-03.
