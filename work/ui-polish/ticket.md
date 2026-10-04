# UI: polish the interface with daisyUI (responsive, accessible, favicon)
Issue: #67 · Branch: feature/ui-polish

## Story
As a learner using Learning Companion on a phone or a desktop, in light or dark mode, I want consistent, readable pages with properly styled forms, buttons and navigation, so that tracking goals, sessions and resources feels clear and pleasant. Today inputs and buttons render as plain text, the header doesn't fit small screens, and most actions are bare links. I also want the app to have its own favicon.

## Acceptance criteria

### Build and themes
- [x] AC1 Tailwind keeps the official binary at its pinned `TAILWIND_CLI_VERSION`. `TAILWIND_CLI_SRC_CSS` points to a committed source stylesheet that loads daisyUI 5 from committed, version-pinned `daisyui.mjs` and `daisyui-theme.mjs` files (the daisyUI version is written down in the repo). A test checks that the setting points to an existing file, that the file loads the plugin, and that both vendored files exist. `manage.py tailwind build` from a clean checkout produces CSS that contains daisyUI component classes (checked by running the build in final-review).
- [x] AC2 The source stylesheet defines two custom daisyUI themes: a light one (`default: true`) and a dark one (`prefersdark: true`), so the dark theme follows `prefers-color-scheme` with no toggle and no JavaScript. Both have an indigo/violet `primary` on neutral slate base colours. A test reads both theme definitions from the stylesheet.
- [x] AC3 In both themes, every content colour on its background has a contrast ratio of at least 4.5:1: `base-content` on `base-100`/`base-200`/`base-300`, and each `*-content` on its colour for `primary`, `secondary`, `accent`, `neutral`, `info`, `success`, `warning` and `error`. A unit test computes the ratios from the colours in the stylesheet.

### Layout (`base.html`, every page)
- [x] AC4 The first focusable element on every page is a skip link to `#main`, and `<main id="main">` exists.
- [x] AC5 Every page has exactly one `<header>`, one `<main>` and one `<footer>`, and every `<nav>` has an accessible name.
- [x] AC6 For a logged-in user, the nav link of the current section (Dashboard, Goals, profile) has `aria-current="page"`, and no other nav link has it.
- [x] AC7 Below the `md` breakpoint the nav links sit in a daisyUI drawer. Its toggle is a real checkbox control with an accessible name ("Menu"). The drawer has the same links as the desktop nav (logged-in and logged-out variants). The test checks the markup; keyboard use is checked in AC27.
- [x] AC8 Log-out stays a POST form with a CSRF token, in both the desktop nav and the drawer.
- [x] AC9 Flash messages render as daisyUI alerts styled by level (`alert-success`, `alert-info`, `alert-warning`, `alert-error`). An error message has `role="alert"` and every other level has `role="status"`.
- [x] AC10 Each page type sets its own `<title>` ending in "· Learning Companion" (the home page keeps "Learning Companion" and the dashboard keeps "Dashboard · Learning Companion"). A test walks every page type and checks that the titles are distinct.
- [x] AC11 Every page type has exactly one `<h1>`, and heading levels never skip (no `h3` straight under an `h1`).

### Favicon
- [x] AC12 `base.html` links a favicon SVG, a `favicon.ico` fallback and a 180×180 `apple-touch-icon` PNG, all committed under `src/assets/`. The mark is an open book or graduation cap in the indigo primary colour. A test checks the links and that the files exist (and the PNG's size).
- [x] AC13 `GET /favicon.ico` while logged out returns 200 with an icon content type (`image/x-icon` or `image/vnd.microsoft.icon`), and the body is the committed `.ico` file.

### Forms
- [x] AC14 Every form outside the admin renders through one project-wide form template: log-in, sign-up, profile edit, goal create and edit, session create and edit, the resource page and the goal page's inline attach form. Each visible control has the matching daisyUI class (`input`, `select`, `textarea`, `checkbox`) and a `<label for>` that matches its `id`.
- [x] AC15 A field with errors has `aria-invalid="true"`, and its `aria-describedby` includes the id of the element showing its error text. Non-field errors (for example a duplicate resource URL, or wrong log-in details) render as an error alert.
- [x] AC16 A field with help text keeps it linked through `aria-describedby` (for example the sign-up password fields).
- [x] AC17 Admin forms aren't affected: the admin add and change pages don't use the project form template, and the existing admin tests stay green.
- [x] AC18 On every non-admin page, every `<button>` and every submit control has the `btn` class. Main actions (save, log in, sign up, attach, generate summary, suggest next steps) are `btn-primary`. The confirm buttons on the three delete pages are `btn-error`.

### Pages and components
- [x] AC19 A goal's status shows as a daisyUI badge that contains the status text, with one badge colour per status, on the goal list and the goal page.
- [x] AC20 Session tags (session list and goal page) and profile focus areas render as a list of badge pills.
- [x] AC21 Every empty state keeps its current wording exactly and shows it in an empty-state block. Where an action exists, the block adds a call-to-action link: no goals → "New goal" (`goals:create`), no sessions on the goal page and the session list → "Add session" (`learning_sessions:create`), no focus areas → "Edit profile". The other empty states (no resources, no summary, no next steps, dashboard without sessions) keep their text in the same styled block.
- [x] AC22 On the dashboard, each per-tag and per-week row has a `<progress>` bar with `value` equal to the row's minutes and `max` equal to the largest value in that table (at least 1, so an all-zero week table still renders). The bar is `aria-hidden="true"` because the table holds the numbers. The dashboard stays at 5 queries.
- [x] AC23 Every data table sits in a horizontally scrollable wrapper (`overflow-x-auto`), so a narrow screen scrolls the table, not the page.
- [x] AC24 The home page shows logged-out visitors "Sign up" and "Log in" calls to action, and logged-in users a link to their dashboard.
- [x] AC25 The goal page's Summary, Next steps, Sessions and Resources sections render as cards, each still labelled by its heading (`aria-labelledby`). The Sessions section, which has no label today, gets `aria-labelledby="sessions-heading"`.

### No behaviour change
- [x] AC26 URLs, views' responses and redirects, form fields and validation, the copy that tests pin, and every `assertNumQueries` pin are unchanged. The full existing suite stays green and lint is clean.

### Visual check (after implementation)
- [ ] AC27 (final-review: Playwright pass) Once every other criterion is implemented, a Playwright pass against the dev server (with the built CSS) checks each page type at 360, 768 and 1280 px wide, in both light and dark colour schemes (`prefers-color-scheme` emulated):
  - no horizontal page scroll (`scrollWidth <= innerWidth`);
  - no unstyled form control or button;
  - a visible focus indicator on links, buttons and form controls;
  - the drawer toggle is reachable with Tab and opens and closes with Space;
  - the drawer's links are reachable with Tab only while it is open.

  The results (and any screenshots) are recorded in `work/ui-polish/review.md`. Every failure becomes a plan step and goes back through `tdd-implement`.

### Documentation
- [x] AC28 `CLAUDE.md` and `README.md` describe:
  - daisyUI and the vendored files (and how to update their version);
  - the themes;
  - the project-wide form rendering and the shared partials;
  - the favicon files and the public `/favicon.ico` route.

## Out of scope
- JavaScript frameworks or runtimes (Alpine, htmx, Flowbite JS), chart libraries, a manual theme toggle
- New pages, features, model fields or URLs (except `/favicon.ico`); copy rewrites beyond the empty-state calls to action and page titles
- Restyling the Django admin
- Docker and CI changes (#20 and #21 pick up the `tailwind build` step and the vendored files)
- Pixel-perfect design review beyond the AC27 checks

## Notes
- Decisions made with the user before the issue was created: daisyUI 5 (chosen over plain Tailwind, Flowbite, django-cotton and the shadcn ports for its low template rework and no Node/JS); light and dark themes following the OS; the "calm & focused" indigo/violet look; a book or graduation-cap favicon; extras in scope: mobile nav, badges, dashboard bars, friendlier empty states.
- Answered in refinement:
  - Visual check: a Playwright pass once everything else is implemented (AC27).
  - Integration: the official Tailwind binary plus committed `daisyui.mjs`/`daisyui-theme.mjs` (daisyUI's documented standalone setup), not the third-party `tailwind-cli-extra` binary.
  - Mobile nav: a daisyUI drawer, not a `<details>` dropdown. Its checkbox mechanism is why AC7 and AC27 spell out keyboard and accessible-name requirements (the default `<label for>` toggle isn't focusable).
  - `/favicon.ico`: a real committed `.ico` file served with a 200, not a redirect.
- Why it looks broken today: templates print a bare `{{ form }}`, and Tailwind's base reset strips input and button borders and backgrounds. The default source stylesheet in `src/.django_tailwind_cli/source.css` holds only `@import "tailwindcss";`.
- Tests check text, ARIA and structure but not CSS classes in app pages, and 17 assertions pin empty-state and "Not set" copy (AC21 keeps that wording). `src/core/tests/html.py`'s `PageParser` is the HTML helper to extend.
- `/favicon.ico` and the static icons must stay public. #42 (`LoginRequiredMiddleware`) must mark the favicon view `@login_not_required`.
- The dashboard bars' `max` can be computed in Python from the rows already fetched (no extra query; AC22).
- Python has no image library here, so the `.ico` and PNG are generated once (for example with the standard library or a macOS tool) and committed; nothing generates them at runtime.
- This ticket goes before #20, #21, #36, #42 and #66, at the user's request.
- **Approval:** the user approved the acceptance criteria (AC1–AC28) on 2026-10-04.
