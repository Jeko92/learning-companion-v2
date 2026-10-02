# Profile: view and edit your own profile
Issue: #6 · Branch: feature/profile-page

## Story
As a logged-in learner, I want to view and edit my own profile (name, cohort and focus areas), and be sure nobody else can see or change it, so that the Learning Companion knows who I am and what I'm focusing on.

## Acceptance criteria
- [x] AC1 Three URLs exist in a `profiles` namespace:
  - `reverse("profiles:mine")` is `/profile/`
  - `reverse("profiles:detail", args=[pk])` is `/profile/<pk>/`
  - `reverse("profiles:edit", args=[pk])` is `/profile/<pk>/edit/`

  `<pk>` is the **profile's** id.
- [x] AC2 All three pages require login. An anonymous `GET` to each, and an anonymous `POST` to the edit URL, redirects to `settings.LOGIN_URL` with `next` set to the requested path. Nothing is saved.
- [x] AC3 `GET /profile/` redirects a logged-in user to their own detail URL. If the user has no profile yet (e.g. loaded from a fixture), one is created first and the redirect goes to it.
- [x] AC4 The detail page shows your own profile.
  - It returns 200 and renders `profiles/profile_detail.html`, which extends `base.html`.
  - `<main>` shows the name, the cohort and the focus areas in name order, plus an "Edit profile" link to `profiles:edit` for this profile.
  - Empty values show "Not set" for the name and cohort, and "No focus areas yet." when there are none.
- [x] AC5 Nobody can see or change another user's profile.
  - User B requesting user A's detail URL, or A's edit URL by `GET` or `POST`, gets **404**, the same as for an id that doesn't exist. So the response doesn't reveal whether the profile exists.
  - The 404 page contains none of A's name, cohort or focus areas, and a `POST` leaves A's profile unchanged.
- [x] AC6 The edit page renders a form for your own profile.
  - It returns 200 and renders `profiles/profile_form.html`, which extends `base.html`.
  - `<main>` has one `method="post"` form whose `action` is the edit URL, with a CSRF token and the inputs `name`, `cohort` and `focus_areas`.
  - The inputs are pre-filled with the current values. `focus_areas` is a single text input holding the tag names comma-separated, in name order.
  - With CSRF checks enforced, a `POST` without a token returns 403 and saves nothing.
- [x] AC7 A valid save updates the profile and redirects.
  - Name and cohort are stored trimmed.
  - The focus areas are set from the comma-separated text:
    - each entry is trimmed, and empty entries are ignored
    - entries that are the same regardless of case are merged
    - each entry becomes a tag through `Tag.objects.get_or_create_by_name()`, so an existing tag is reused with its existing spelling
    - an entry removed from the text is removed from the profile, but the `Tag` itself is not deleted
  - The response redirects to the detail page, which shows "Profile saved.".
- [x] AC8 Invalid input re-renders the form (200) with field errors and saves nothing: no field changes and no new tags.
  - A blank or whitespace-only name gives "This field is required." on `name`.
  - A name over 100 characters or a cohort over 50 gives the standard length error on that field.
  - A focus-area entry over 50 characters, or one rejected by AC9, gives an error on `focus_areas` that names the entry.
- [x] AC9 Tag names are normalised before matching or storing. This lives in `tags` and applies to every `get_or_create_by_name` call.
  - **Unicode:** names are NFKC-normalised. Full-width "ＰＹＴＨＯＮ" finds "Python", and "café" typed precomposed or decomposed is one tag.
  - **Whitespace:** internal whitespace runs collapse to a single space, so "Machine   Learning" is stored as "Machine Learning".
  - **Rejected characters:** names containing control or format characters (e.g. NUL `\x00`, or the zero-width space U+200B) raise `ValidationError`, and no tag is created.
  - **Validation first:** the name is validated *before* the database lookup. A 50,001-character name raises `ValidationError`, not a database error.
- [x] AC10 Your pages never show other users' data.
  - With users A and B having different names, cohorts and focus areas (one tag shared, one tag unique to A), B's detail page and B's edit page contain none of A's name, cohort or A-only tag.
  - The edit form offers no list of existing tags: there is no `<select>`, and there are no checkboxes of tags.
- [x] AC11 The logged-in nav links to your profile. The username becomes a link to `profiles:mine`.
  - The logged-in nav's exact text stays "Goals alice Log out".
  - `links("nav")` is `[(reverse("profiles:mine"), "alice")]`.
  - The anonymous nav is unchanged.
  - This deliberately changes #4's AC10 ("no links" when logged in), and its nav test is updated in the same step.
- [x] AC12 Profile values are shown escaped. A name, cohort and focus area containing `<script>alert(1)</script>` appear only escaped on the detail page and in the edit form, never as raw markup.

## Out of scope
- Public profiles, profiles of other users, avatars.
- Suggesting or listing tags, including the user's own earlier tags, beyond what the field already holds.
- Deleting or renaming `Tag` rows (the admin only), and cleaning up unused tags.
- A `casefold()` key column for full Unicode case-insensitivity. Case folding stays ASCII-only on SQLite (#5); NFKC (AC9) covers width and composition variants.
- Changing the username or password.
- The deferred lows from #5 that this ticket doesn't need: the race test's "miss happened" assertion, and re-raising a non-unique `IntegrityError`.

## Notes
Answers from refinement (2026-10-02):
- **URL: `/profile/<id>/` with a 404 for anyone else**, the user's choice over the #5 guidance's "no id in the URL".
  - This makes ownership checks central: every view taking an id finds the profile **only among the logged-in user's own**, so another user's id and a missing id both give the same 404 (AC5). That is tested for detail, and for edit by `GET` and `POST`.
  - `/profile/` is a convenience URL that redirects to your own profile. The nav links there (AC11), so the id never has to be known.
  - The id is the profile's primary key, not the user's.
- **A view page plus a separate edit page.** Saving redirects to the view page with "Profile saved.", following the post/redirect/get pattern.
- **Focus areas: one comma-separated text field.** Typed entries go through `get_or_create_by_name`, and there is no all-tags picker. The #5 security notes say that would expose other users' tag text.
- **Tag-name normalisation is part of this ticket (AC9),** because this is the first ticket where users type tags. It follows the guidance on issue #6: NFKC, reject control and format characters, validate before the lookup.
- **Name is required and cohort optional** on the edit form. The model keeps both `blank=True` (#5), because auto-created profiles start empty. Focus areas may be empty.
- **Defaults I chose** (say if you want them changed):
  - "Not set" / "No focus areas yet." placeholders
  - tags listed in name order
  - "Profile saved." as the message
  - 404, not 403, so others' profiles aren't revealed
  - the username in the nav as the profile link

Constraints and context:
- `LOGIN_URL = "accounts:login"` already exists (#4), and nothing uses `login_required` yet; these are the first login-required pages.
- Profiles for users created outside `save()` (fixtures, `bulk_create`) may be missing. `/profile/` uses `Profile.objects.get_or_create(user=request.user)` (CLAUDE.md), and `<pk>` lookups are scoped to `request.user`.
- The logged-in nav test (`accounts/tests/test_nav.py`) pins `links("nav") == []`. AC11 changes it deliberately.
- `CLAUDE.md` (Layout, Stack) and `README.md` get the profile URLs and the tag normalisation rule. The plan includes this.
- Depends on #4 and #5, both done.

Status: the user approved these acceptance criteria (AC1–AC12) on 2026-10-02. The next step is `plan-ticket`.
