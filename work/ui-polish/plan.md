# Plan: ui-polish

## Research summary

**Templates and pages.** All 17 templates live in `src/templates/` (no app template dirs, no registration/404 pages).
- `base.html` holds the header, nav, messages, `<main>` and footer. Only `dashboard.html` sets `{% block title %}`.
- Bare `{{ form }}` renders: `accounts/login.html:7`, `accounts/signup.html:7`, `profiles/profile_form.html:7`, `goals/goal_form.html:8`, `learning_sessions/session_form.html:9`, `resources/resource_form.html:8`, plus `{{ resource_form }}` at `goals/goal_detail.html:85`.
- Unstyled buttons: `base.html:20`, all form pages, `goal_detail.html:86`.
- Partial: `learning_sessions/_session_item.html`, used by the goal page and the session list.
- Messages: success, info and error are used (warning isn't). `MESSAGE_TAGS` isn't set, so the default tags are `success`/`info`/`warning`/`error`.
- Dashboard context: `status_rows`, `total_goals`, `tag_rows`, `week_rows`. Every row set is already a Python list after 3 queries, so the bar maxima cost nothing. `tag_rows` isn't sorted by max (Untagged comes last), and `week_rows` can be all zeros.
- Static files: default `StaticFilesStorage`, no `{% load static %}` anywhere, `STATICFILES_DIRS = [BASE_DIR / "assets"]`. `BASE_DIR` is `src/`.

**Forms.** `SignUpForm(UserCreationForm)` (`accounts/forms.py:5`). Login uses Django's stock `AuthenticationForm` (`LogInView`, `accounts/views.py:34`). `GoalForm` (`goals/forms.py:6`), `LearningSessionForm` (`learning_sessions/forms.py:10`, date widget set in `__init__`), `ProfileForm` (`profiles/forms.py:9`), `ResourceForm` (`resources/forms.py:7`); `TagListField` is a `CharField` with help text. None sets a template, renderer or widgets.

**Django 6.1.1 form rendering.**
- The default `DjangoTemplates` renderer doesn't search `TEMPLATES["DIRS"]`. `TemplatesSetting` does, but it needs `"django.forms"` in `INSTALLED_APPS`.
- `Form.template_name` and `BoundField.template_name` can be overridden per class. `bound_field_class` exists on renderer, form and field.
- `BoundField.build_widget_attrs` already adds `aria-invalid="true"` (field with errors) and `aria-describedby="<auto_id>_helptext <auto_id>_error"`. The error list gets `id="<auto_id>_error"`, the help text `id="<auto_id>_helptext"`.
- `Widget.build_attrs` lets returned attrs *replace* the widget's own `class`, so any class addition must merge in `widget.attrs["class"]`.
- Admin templates never render `{{ form }}`/`as_field_group` (they render `{{ field.field }}`), except management forms, which use `form_template_name` (hidden fields only). Admin widgets share the core widget and error-list templates, so don't override `django/forms/*`.
- Non-field errors: `ErrorList(error_class="nonfield")`, no id. A failed log-in is a non-field error, and the username/password inputs get no `aria-invalid`.

**Tailwind and daisyUI build.**
- `TAILWIND_CLI_SRC_CSS` is relative to `BASE_DIR` (`src/`). Once set, the file is user-owned and the old `.django_tailwind_cli/source.css` is no longer used.
- The source must not live under `src/assets/`: check W001 warns, because `collectstatic` would publish it.
- The CLI runs with `cwd=src/`: `<binary> --input <src_css> --output src/assets/css/tailwind.css --minify`. Source detection scans `src/`, honours `.gitignore`, and reads `.py` files too. The committed `.mjs` files must be excluded with `@source not "./daisyui{,*}.mjs";` (without it the build is about 10× larger).
- daisyUI latest is **5.7.47** (`https://github.com/saadeghi/daisyui/releases/download/v5.7.47/daisyui.mjs` and `.../daisyui-theme.mjs`). A trial build with `@plugin "./daisyui.mjs" { themes: false; }` plus a custom `@plugin "./daisyui-theme.mjs" { name; default; prefersdark; color-scheme; --color-*; --radius-*; --size-*; --border; --depth; --noise }` worked and gave about 56 KB minified for these templates.
- Dynamic class names (for example `alert-{{ message.tags }}`) aren't detected. Every class must appear literally in a template or `.py` file, or be listed in `@source inline("...")`.

**daisyUI drawer.**
- Markup: `.drawer > input#<id>.drawer-toggle + .drawer-content + .drawer-side > label.drawer-overlay + menu`.
- A closed `.drawer-side` is `visibility:hidden`, so its links can't be reached with Tab and screen readers skip them. The toggle checkbox stays focusable (0×0, opacity 0), and `.drawer-toggle:focus-visible ~ .drawer-content label.drawer-button` gets an outline.
- `md:drawer-open` keeps the sidebar visible from `md` up. There's no focus trap or Escape support (accepted: no JS).

**Favicons.** No Pillow, `rsvg-convert` or ImageMagick on this machine. `sips` renders SVG to PNG cleanly at any size, and a short stdlib script packs 16/32/48 PNGs into an ICO. Commit the generated files. The apple-touch PNG needs an opaque, full-bleed background.

**Tests.**
- Django runner: `TestCase`, objects created in `setUp`, `force_login`, `PASSWORD = "Tr4ck-Learning!"`.
- Class names follow `<Thing><Aspect>Tests`, and method names are full sentences.
- Page tests use a module-level `get_page()` and `core/tests/html.py`'s `PageParser`: `text(section)`, `links(section)`, `forms(section)` (inputs only), and `.elements` (every start tag on the page). Sections are title/header/nav/main/footer, and contents of all same-named sections are merged.
- The suite has 459 tests (about 39 s), and the post-write hook runs it after every `src/` write.
- `assertNumQueries` pins: dashboard 5, goal detail 7, session list 6. Nothing pins `base.html` queries, so any layout query would raise all three.

**Markup traps (existing tests that must keep passing).**
- `accounts/tests/test_nav.py` checks `links("nav")` and `text("nav")` for exact equality (anonymous: "Log in Sign up"; logged in: "Dashboard Goals alice Log out") and exactly one form in `nav`. `test_logout.py:157` checks the same form with one CSRF token. So the links exist **once**, in a single `<nav>`, with no other text or links inside it (the toggle label and the brand stay outside every `<nav>`).
- `profiles/tests/test_views.py:324-331` forbids any `<input type="checkbox">` on the profile edit page. The drawer toggle breaks it (step 7).
- `accounts/tests/test_signup.py:46`: the sign-up page has exactly one `<form>`, whose attrs are exactly `{method, action}` (no class on that form).
- `resources/tests/test_views.py:69-74`: the named inputs on the page are exactly `{csrfmiddlewaretoken,url,title,type}`, so the drawer checkbox has no `name`.
- Many tests do `((form,_),) = page.forms("main")`: one form inside `<main>` on form and delete pages.
- `goals/tests/test_views.py:700`: exactly one `<span … aria-current="page">TEXT</span>` with no child tags (the active status filter). Nav links use `<a aria-current>`.
- `<h1>Dashboard</h1>` (regex, no inner tags). The title stays "Dashboard · Learning Companion".
- `core/tests/test_home.py:118`: `<link rel="stylesheet" href="/static/css/tailwind.css">` stays exactly as it is, so `DIST_CSS` doesn't change.
- Dashboard table rows are compared as exact cell texts (`["Untagged","2 h"]`), so a bar goes inside the existing Time `<td>` with no text (no fallback text inside `<progress>`). `hours.text() == "Hours per tag No sessions logged yet."` holds exactly, so no extra text in that section when it's empty.
- Goal page:
  - Resources section text starts with "Resources Articles A tutorial Delete".
  - The Summary text starts with "Summary".
  - The next-steps text must not contain "new" when empty, and its `<ol><li>` texts equal the plain steps.
  - `>Sessions</h2>` raw.
  - The resource title appears exactly twice.
- Pagination: no disabled Previous/Next rendered, and filter links never contain `page=`.
- Icons are inline `<svg aria-hidden="true">` with no text nodes, so `text()` assertions are unaffected.

## Design decisions
1. **Source files live in `src/tailwind/`**: `source.css`, `daisyui.mjs` and `daisyui-theme.mjs` (5.7.47). `TAILWIND_CLI_SRC_CSS = "tailwind/source.css"`. Not under `assets/`, so nothing is published by `collectstatic` (check W001). `source.css`'s header comment records the daisyUI version, the download URLs and each file's sha256; a test verifies the hashes.
2. **Themes:** `@plugin "./daisyui.mjs" { themes: false; }` (no built-in themes, smaller CSS) plus two custom themes: `companion` (light, `default: true`) and `companion-dark` (`prefersdark: true`). Indigo/violet primary (oklch hue about 265–290) on slate bases, rounded boxes. A unit test converts the oklch colours to sRGB and checks the WCAG contrast pairs.
3. **App shell:**
   - `base.html` becomes a daisyUI drawer with `md:drawer-open`: a slide-in drawer below `md` and a persistent sidebar from `md` up.
   - The single `<nav aria-label="Main">` lives in `.drawer-side`, so the nav links are rendered once. That satisfies the exact-equality nav tests and keeps the closed drawer's links out of the Tab order.
   - `.drawer-content` holds the `<header>` (navbar with the brand link and, below `md`, the `label.drawer-button` toggle), the messages, `<main id="main">` and the `<footer>`.
   - The toggle checkbox (`id="nav-drawer"`, no `name`, `aria-label="Menu"`, `md:hidden`) is the focusable control.
   - Logged-out visitors get the same shell with Log in / Sign up.
4. **Forms:**
   - A `StyledFormMixin` in `src/core/forms.py` sets `template_name = "forms/div.html"` and `bound_field_class = StyledBoundField`.
   - `StyledBoundField` sets `template_name = "forms/field.html"`. Its `build_widget_attrs` merges the daisyUI class by widget type: `input w-full` for text-like inputs, `textarea w-full`, `select w-full`, `checkbox`, `radio`. It adds the matching `*-error` class when the field has errors.
   - `FORM_RENDERER = "django.forms.renderers.TemplatesSetting"` and `"django.forms"` in `INSTALLED_APPS`, so the project's `src/templates/forms/*.html` are found and Django's own form templates still resolve.
   - Every project form uses the mixin, including a new `LogInForm(StyledFormMixin, AuthenticationForm)` set as `LogInView.authentication_form`.
   - The admin keeps its default form classes, so nothing about it changes. No `django/forms/*` template is overridden.
   - `forms/field.html` keeps Django's `<auto_id>_helptext` and `<auto_id>_error` ids, so the built-in `aria-describedby`/`aria-invalid` keep working. `forms/div.html` renders non-field errors as `<div role="alert" class="alert alert-error">`.
5. **Messages:** `alert` plus a literal class per level through `{% if %}` branches (Tailwind can't see dynamic names). `role="alert"` for `error`, `role="status"` for the rest.
6. **Shared partials** in `src/templates/components/` via `{% include … with … %}`:
   - `_page_header.html`: h1, optional subtitle, actions
   - `_empty_state.html`: icon, text, optional CTA
   - `_status_badge.html`: literal badge class per `Goal.Status`
   - `_tag_list.html`: pills
   - `_confirm_delete.html`: card with the warning lines, a `btn-error` form and Cancel

   Icons are inline heroicons (MIT) SVG with `aria-hidden="true"`.
7. **Status badge colours:** planned → `badge-neutral`, in-progress → `badge-info`, done → `badge-success`. The text label is always inside the badge.
8. **Empty-state CTAs** appear alongside the existing action links (no link is removed), so existing link assertions keep passing.
9. **Dashboard bars:** the view adds `tag_max` and `week_max` (`max(…, default=0) or 1`), computed from the rows already fetched, so no query is added. Each Time `<td>` gets `<progress class="progress progress-primary" value=… max=… aria-hidden="true"></progress>` under the duration text.
10. **Favicon:**
    - Files: a hand-written `src/assets/favicon.svg` (open book, indigo), plus `apple-touch-icon.png` (180×180, opaque) and `favicon.ico` (16/32/48 PNG entries), generated once with `sips` and a stdlib packing script and committed. The commands go in the README.
    - `base.html` links them with `{% static %}`.
    - `core.views.favicon` serves `/favicon.ico` as a `FileResponse` (`image/x-icon`, public, cacheable) from `core/urls.py`.
11. **Page titles:** `<Page> · Learning Companion`, with a dynamic part where needed (for example `{{ goal.title }} · Learning Companion`). Home keeps "Learning Companion" and the dashboard keeps its title.
12. **Shared test helper:** `src/core/tests/pages.py` builds the fixture (alice with one goal, one session with a tag, one resource) and returns every page type as `(name, path, logged_in)`. The layout, title, heading, button and form tests walk it, so a new page type is added there deliberately.
13. **Test-only code:**
    - The oklch→sRGB→WCAG conversion lives in `src/core/tests/test_theme.py`.
    - `PageParser` gains no new section types: tests use `.elements` and the existing helpers. A small `headings()`/`buttons()` helper is added to `html.py` only if two or more tests need it.

## Steps
- [x] 1. The Tailwind build uses a committed source stylesheet that loads the vendored, hash-pinned daisyUI 5.7.47 plugin files. Download both `.mjs` files with `curl` into `src/tailwind/` (a Bash download doesn't trigger the post-write hook, so the next file written through Write/Edit records the test result). Then run `manage.py tailwind build` once and confirm `.btn` is in the output. — test: `src/core/tests/test_theme.py` (`TailwindSourceTests`: the setting points to an existing file, which has `@plugin "./daisyui.mjs"` and `@source not "./daisyui{,*}.mjs"`, and both vendored files exist with the sha256 recorded in the header) — impl: `src/config/settings.py`, `src/tailwind/source.css`, `src/tailwind/daisyui.mjs`, `src/tailwind/daisyui-theme.mjs` — covers: AC1
- [x] 2. Two custom themes, `companion` (default, light) and `companion-dark` (prefersdark, dark). Each defines every required colour, radius and size variable with an indigo/violet primary, and every content colour meets 4.5:1 on its background. — test: `src/core/tests/test_theme.py` (`ThemeTests`: parse both `@plugin "./daisyui-theme.mjs"` blocks, flags, primary hue range, and the contrast of every AC3 pair through an oklch→sRGB→relative-luminance helper) — impl: `src/tailwind/source.css` — covers: AC2, AC3
- [x] 3. Shared page fixture, plus a skip link that is the first focusable element on every page and targets `<main id="main">`. — test: `src/core/tests/pages.py` (new helper), `src/core/tests/test_layout.py` (`SkipLinkTests`, walking every page type) — impl: `src/templates/base.html` — covers: AC4
- [x] 4. Page structure: exactly one `header`, `main` and `footer`, every `nav` has an accessible name, exactly one `<h1>` per page, and no skipped heading levels. — test: `src/core/tests/test_layout.py` (`PageStructureTests`) — impl: `src/templates/base.html` (`aria-label` on the main nav and the pagination/filter navs already have one); fix any template that fails the heading rule — covers: AC5, AC11
- [x] 5. The nav link of the current section has `aria-current="page"`: Dashboard on `dashboard:*`; Goals on `goals:*`, `learning_sessions:*` and `resources:*`; the profile link on `profiles:*`. No other nav link has it. — test: `src/accounts/tests/test_nav.py` (`NavCurrentPageTests`) — impl: `src/templates/base.html` (`request.resolver_match.namespace`, no query) — covers: AC6
- [x] 6. Flash messages render as daisyUI alerts by level: `alert-success`, `alert-info`, `alert-warning`, `alert-error`, with `role="alert"` on errors and `role="status"` on the rest. — test: `src/core/tests/test_layout.py` (`MessageTests`: a tiny test-only view, or `messages` added through a real flow per level, e.g. log-out for info, an AI error for error; warning through a request with `messages.add_message`) — impl: `src/templates/base.html` — covers: AC9
- [x] 7. **Test fix (deliberate, its own commit):** the profile edit test that forbids any `<input type="checkbox">` on the page is narrowed to the profile form inside `<main>`. Its intent is that focus areas aren't a checkbox list; the coming nav drawer adds a page-level checkbox that has nothing to do with the form. No production change; the suite stays green. — test: `src/profiles/tests/test_views.py:324-331` — impl: none — covers: AC26 (keeps the suite truthful for AC7)
- [x] 8. App shell with a drawer:
  - a `.drawer.md:drawer-open` wrapper and a toggle checkbox (`id="nav-drawer"`, `aria-label="Menu"`, no `name`);
  - a `label.drawer-button` toggle in the header (below `md`);
  - one `<nav aria-label="Main">` in `.drawer-side` with the existing links (the logged-in and logged-out variants) and the log-out POST form with CSRF;
  - an overlay label outside the nav;
  - a navbar header with a brand link to `home`, and a styled footer.

  The existing nav and log-out tests stay green unchanged. — test: `src/accounts/tests/test_nav.py` (`NavDrawerTests`: the toggle checkbox with its accessible name, the nav inside `.drawer-side`, the log-out form inside that nav, no nav links outside it) — impl: `src/templates/base.html` — covers: AC7, AC8
- [x] 9. Each page type sets its own `<title>` ending in "· Learning Companion". Home stays "Learning Companion" and the dashboard stays the same; all titles are distinct across the fixture's pages. — test: `src/core/tests/test_layout.py` (`PageTitleTests`) — impl: `{% block title %}` in every page template — covers: AC10
- [x] 10. `base.html` links `favicon.svg` (`type="image/svg+xml"`), `favicon.ico` (`sizes="32x32"` or `any`) and `apple-touch-icon.png`. The files exist under `src/assets/`, and the PNG is 180×180 (read from its IHDR chunk). — test: `src/core/tests/test_favicon.py` (`FaviconLinkTests`) — impl: `src/assets/favicon.svg`, `src/assets/apple-touch-icon.png`, `src/assets/favicon.ico` (generated with `sips` and a stdlib ICO packer), `src/templates/base.html` (`{% load static %}`) — covers: AC12
- [x] 11. `GET /favicon.ico`, logged out, returns 200 with `image/x-icon`, and its body is the committed file. — test: `src/core/tests/test_favicon.py` (`FaviconRouteTests`) — impl: `src/core/views.py` (`favicon`), `src/core/urls.py` — covers: AC13
- [x] 12. Project-wide form rendering:
  - `StyledFormMixin`, `StyledBoundField`, `forms/div.html` and `forms/field.html`;
  - `TemplatesSetting` plus `django.forms`;
  - the mixin on `SignUpForm`, `ProfileForm`, `GoalForm`, `LearningSessionForm`, `ResourceForm` and a new `LogInForm` (wired into `LogInView`).

  On every form page (log-in, sign-up, profile edit, goal create/edit, session create/edit, resource page, the goal page's inline attach form), every visible input/select/textarea has its daisyUI class and a `<label for>` matching its id. Help text stays linked through `aria-describedby` (the sign-up password and the tags field). The admin add and change pages for a goal render no daisyUI field classes and none of the project field markup. — test: `src/core/tests/test_forms.py` (`StyledFormRenderingTests`, `AdminFormsUnchangedTests`) — impl: `src/core/forms.py`, `src/templates/forms/div.html`, `src/templates/forms/field.html`, `src/config/settings.py`, `src/accounts/forms.py`, `src/accounts/views.py`, `src/profiles/forms.py`, `src/goals/forms.py`, `src/learning_sessions/forms.py`, `src/resources/forms.py` — covers: AC14, AC16, AC17
- [x] 13. A field with errors has `aria-invalid="true"`, its error element's id is in its `aria-describedby`, and its control carries the `*-error` class (e.g. a blank goal title). Non-field errors (a duplicate resource URL, wrong log-in details) render inside `role="alert"` `.alert.alert-error`. — test: `src/core/tests/test_forms.py` (`FormErrorTests`) — impl: `src/core/forms.py`, `src/templates/forms/div.html`, `src/templates/forms/field.html` — covers: AC15
- [x] 14. Every `<button>` on every page in the fixture walk has `btn`. The main actions are `btn-primary`: save, log in, sign up, attach resource, generate/regenerate summary, suggest next steps. The confirm button on all three delete pages is `btn-error`. Cancel and secondary links are styled as `btn btn-ghost`/`btn-outline` (not asserted). Delete pages move to `components/_confirm_delete.html`; page headers move to `components/_page_header.html`. — test: `src/core/tests/test_layout.py` (`ButtonTests`) — impl: all page templates, `src/templates/components/_page_header.html`, `src/templates/components/_confirm_delete.html` — covers: AC18
- [x] 15. A goal's status shows as a badge containing the status label, with a distinct literal badge class per status, on the goal list rows and the goal page header. The goal list becomes card rows; the status filter becomes a `tabs tabs-box` group (the active entry stays the `<span aria-current="page">`); pagination becomes a `join` group. — test: `src/goals/tests/test_views.py` (`GoalStatusBadgeTests`) — impl: `src/templates/components/_status_badge.html`, `src/templates/goals/goal_list.html`, `src/templates/goals/goal_detail.html` — covers: AC19
- [x] 16. Session tags (session list and goal page) and profile focus areas render as a `<ul>` of `badge` pills. The profile page becomes a card. — test: `src/learning_sessions/tests/test_views.py` (`SessionTagPillTests`), `src/profiles/tests/test_views.py` (`FocusAreaPillTests`) — impl: `src/templates/components/_tag_list.html`, `src/templates/learning_sessions/_session_item.html`, `src/templates/profiles/profile_detail.html` — covers: AC20
- [x] 17. Every empty state renders its exact current text inside a `components/_empty_state.html` block (an element with a stable class or `data-empty-state` marker). The CTAs: no goals → "New goal" (`goals:create`); no sessions on the goal page and the session list → "Add session" (`learning_sessions:create`); no focus areas → "Edit profile" (`profiles:edit`). The others (no goals with this status, no resources, no summary, no next steps, dashboard without sessions, "Not set") keep their text with no CTA, and "No sessions logged yet." stays the only text in its section. — test: `src/core/tests/test_empty_states.py` (`EmptyStateTests`, one per state) — impl: `src/templates/components/_empty_state.html`, `goal_list.html`, `goal_detail.html`, `session_list.html`, `profile_detail.html`, `dashboard.html` — covers: AC21
- [x] 18. Each per-tag and per-week dashboard row has a `<progress>` inside its Time cell, with `value` = the row's minutes, `max` = the table's largest value (at least 1, so an all-zero week table renders `max="1"`) and `aria-hidden="true"`. The row cell texts and the 5-query pin are unchanged. (Dropped while implementing: a `stats` card for the "Goals by status" total; that section's text is pinned exactly and the Total row already shows it.) — test: `src/dashboard/tests/test_views.py` (`DashboardBarTests`) — impl: `src/dashboard/views.py` (`tag_max`, `week_max`), `src/templates/dashboard/dashboard.html` — covers: AC22
- [x] 19. Every `<table>` on every page sits inside an `overflow-x-auto` wrapper and carries daisyUI's `table` class. — test: `src/core/tests/test_layout.py` (`TableWrapperTests`) — impl: `src/templates/dashboard/dashboard.html` — covers: AC23
- [x] 20a. **Test fix (deliberate, its own commit; added while implementing, approved by the user):** `core/tests/test_home.py::test_logged_in_visitors_get_the_same_home_page_not_a_redirect` asserted an identical `<main>` for both visitors, which contradicts AC24. It is narrowed to its intent: `/` answers 200 with `home.html` for a logged-in user (no redirect), and the heading and pitch are the same for both. No production change. — test: `src/core/tests/test_home.py` — impl: none — covers: AC26 (keeps the suite truthful for AC24)
- [x] 20. Home page hero. Logged out, it shows "Sign up" (`btn-primary`) and "Log in" calls to action in `<main>`; logged in, it shows a "Go to your dashboard" link instead and no sign-up CTA. — test: `src/core/tests/test_home.py` (`HomeCallToActionTests`) — impl: `src/templates/home.html` — covers: AC24
- [x] 21. On the goal page, Summary, Next steps, Sessions and Resources are `card`s labelled by their heading. The Sessions section gets `aria-labelledby="sessions-heading"` with `<h2 id="sessions-heading">Sessions</h2>`, and the goal page's description, metadata and actions get the page header and card styling. — test: `src/goals/tests/test_views.py` (`GoalDetailCardTests`: each of the four sections is a `section.card` whose `aria-labelledby` names an existing `h2`) — impl: `src/templates/goals/goal_detail.html` — covers: AC25
- [x] 22. Documentation:
  - `CLAUDE.md`:
    - Stack: daisyUI 5.7.47 vendored in `src/tailwind/`, how to update it (download, sha256, header comment), the two themes, `StyledFormMixin` and `forms/*.html` (every new form must use the mixin), `components/` partials, the drawer shell and nav rules, favicon files and the public `/favicon.ico`.
    - Layout: `src/tailwind/`, `src/templates/forms/`, `src/templates/components/`.
  - `README.md`: the build step and how the favicons are regenerated.

  No `src/` change. — test: none (docs) — impl: `CLAUDE.md`, `README.md` — covers: AC28

### Review findings (final-review 2026-10-04, `review.md`)
- [ ] 23. Light-theme contrast of faded daisyUI text: the dashboard tables' `thead`/`tfoot` rows and the goal list's inactive filter tabs render at full `base-content` colour (a literal utility such as `text-base-content`, which beats daisyUI's faded component colour), so they reach 4.5:1 (measured 4.09:1 and 3.03:1). — test: `src/core/tests/test_layout.py` (`FadedTextTests`: every `thead`/`tfoot` on the dashboard and every inactive `.tab` link on the goal list carry the full-colour class) — impl: `src/templates/dashboard/dashboard.html`, `src/templates/goals/goal_list.html` — covers: AC2 (re-checked by the Playwright contrast audit in the re-review)
- [ ] 24. A clearly visible keyboard focus indicator on the sidebar menu's links and button: a `:focus-visible` outline (2px, `--color-primary`, offset) for `.menu` items in the source stylesheet. — test: `src/core/tests/test_theme.py` (`FocusStyleTests`: the stylesheet has a `.menu` `:focus-visible` rule with an outline in the primary colour) — impl: `src/tailwind/source.css` — covers: AC2, AC27
- [ ] 25. Drawer focus order: `.drawer-side` comes right after the toggle checkbox and before `.drawer-content`, so opening the drawer with Space puts the nav links next in the Tab order. The skip link stays the first focusable element and the nav is still rendered once. — test: `src/accounts/tests/test_nav.py` (`NavDrawerTests`: document order is toggle, then `.drawer-side`, then `.drawer-content`) — impl: `src/templates/base.html` — covers: AC7, AC27 (desktop sidebar and mobile drawer re-checked with Playwright in the re-review)
- [ ] 26. Resource titles on the goal page wrap at word boundaries (`break-words`, not `break-all`); the delete page's raw URL keeps `break-all`. — test: `src/goals/tests/test_views.py` (`GoalDetailCardTests`: the resource title link has `break-words` and not `break-all`) — impl: `src/templates/goals/goal_detail.html` — covers: AC1/AC26 visual polish (review low finding)
- [ ] 27. Direct tests for `StyledBoundField` and a wider admin check (test-only, no production change unless a test exposes a bug): an ad-hoc `StyledFormMixin` form proves the merge with a widget's own `class`, no classes on a `HiddenInput`, and the `select-error`/`textarea-error`/`checkbox-error` variants; `AdminFormsUnchangedTests` also covers the user change page (profile inline, tag autocomplete). — test: `src/core/tests/test_forms.py` (`StyledBoundFieldTests`, `AdminFormsUnchangedTests`) — impl: none expected — covers: AC14, AC15, AC17

**Coverage:**
- AC1 → 1 (plus the build run in final-review)
- AC2, AC3 → 2
- AC4 → 3
- AC5, AC11 → 4
- AC6 → 5
- AC7, AC8 → 8 (prepared by 7)
- AC9 → 6
- AC10 → 9
- AC12 → 10
- AC13 → 11
- AC14, AC16, AC17 → 12
- AC15 → 13
- AC18 → 14
- AC19 → 15
- AC20 → 16
- AC21 → 17
- AC22 → 18
- AC23 → 19
- AC24 → 20 (prepared by 20a)
- AC25 → 21
- AC26 → every step (full suite green after each, query pins untouched) and 7
- AC2, AC27 → also 23–25 (review findings)
- AC27 → final-review: Playwright pass on the dev server with the built CSS, recorded in `review.md`; failures become new steps here
- AC28 → 22

**Notes for implementation:**
- Restyle each template in the step that touches it (cards, spacing, `btn` links). A template only needs to be finished by the step that names it, and the layout of every page is complete after step 21.
- Every class must appear literally in a template or `.py` file (no `alert-{{ tag }}`).
- Run `./.venv/bin/python src/manage.py tailwind build` after steps 1, 2, 8 and 21 to make sure the build still succeeds. The built CSS is git-ignored and never committed.
