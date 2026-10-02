# Review: profile-page

## Verdict: FAIL

The security review found one **high** finding: the focus-areas input is unbounded, so a single save can block the shared SQLite database. The code review found two **medium** findings: full-width commas aren't treated as separators, and AC7's case-merge rule has no test that can fail.

Apart from these, ownership, IDOR protection, CSRF and XSS were all confirmed sound, mostly with mutations. The suite is green (125 tests, also with `--parallel 4 --shuffle`), lint is clean, and `makemigrations --check` is clean.

## Acceptance criteria
- AC1: covered by `ProfileDetailTests.test_your_own_profile_page_is_served`, `MyProfileTests.test_sends_you_to_your_own_profile` and `ProfileEditTests.test_edit_page_renders_your_profile_in_a_form`. PASS
- AC2: covered by the three `…anonymous_visitors_are_sent_to_log_in…` tests (detail, mine, and edit by GET and POST). PASS
- AC3: covered by `MyProfileTests.test_creates_a_missing_profile_first`. PASS, but the precondition is unasserted (finding 8).
- AC4: covered by `ProfileDetailTests` (served, values or placeholders) and `ProfileEditTests.test_detail_page_links_to_the_edit_page`. PASS
- AC5: covered by `ProfileDetailTests.test_another_users_profile_or_a_missing_one_is_not_found` and `ProfileEditTests.test_another_user_cannot_see_or_change_your_profile`. PASS on status. The "no data in the 404 body" checks are vacuous (finding 7).
- AC6: covered by `ProfileEditTests.test_edit_page_renders_your_profile_in_a_form` and `ProfileEditCsrfTests`. PASS
- AC7: covered by `ProfileEditTests.test_a_valid_save_stores_trimmed_values_and_redirects` and `FocusAreasInputTests.test_focus_areas_are_set_from_comma_separated_text`. **Partly covered:** case merging survives mutation (finding 3).
- AC8: covered by `ProfileEditTests.test_invalid_input_rerenders_the_form_and_saves_nothing` and `FocusAreasInputTests.test_an_invisible_character_is_a_field_error_and_saves_nothing`. PASS
- AC9: covered by the five `tags.tests.test_models.NameNormalisationTests`. PASS
- AC10: covered by `ProfilePrivacyTests` (both tests). PASS
- AC11: covered by `accounts.tests.test_nav…test_logged_in_nav_links_the_username_to_the_profile_and_has_logout`. PASS
- AC12: covered by `ProfileEscapingTests`. PASS

## Findings
1. **[high] (security; code low) `src/profiles/forms.py:11-13,32,48-54`: there is no limit on focus-area input.**
   - **Problem:** the `focus_areas` field has no `max_length`, and there is no cap on the number of entries. Only Django's 2.5 MB request limit applies, which allows around 500,000 entries in one save.
   - **Why it matters:**
     - Each entry runs an `iexact` (`LIKE`) lookup that scans the whole tag table, and may insert a tag. All of it happens inside `@transaction.atomic`, after the profile row has been written, so SQLite's write lock is held throughout. Other users' logins, sign-ups and saves then fail with "database is locked".
     - Any user can sign up and do this repeatedly. Even saves that succeed permanently grow the shared tag table.
     - A very large `set()` can also exceed SQLite's variable limit and cause a 500.
   - **Fix:** step 19 (AC13).
2. **[medium] (code) `src/profiles/forms.py:32`: a full-width comma (U+FF0C, also U+FE50 and U+FE10) is only normalised after the split.**
   - **Problem:**
     - "Python，Django" is stored as one tag, "Python,Django".
     - Re-saving the form unchanged then splits it into two tags.
     - A comma inside a tag name breaks the comma-separated round trip.
   - **Fix:** step 20.
3. **[medium] (code) `src/profiles/tests/test_forms.py:23-35`: AC7's "entries that are the same regardless of case are merged" survives mutation.**
   - **Problem:** with the form's de-duplication removed, the test stays green, because the database's `iexact` already merges ASCII case.
   - **When it matters:** only for non-ASCII case. Without it, "Élan, élan" gives two tags.
   - **Fix:** step 21.
4. **[low] (code) `src/profiles/forms.py:23-25,48-55`: two latent form bugs.**
   - **Problem:**
     - `save(commit=False)` writes the M2M and creates tags immediately, and raises `ValueError` on an unsaved instance.
     - An unbound `ProfileForm()` crashes in `__init__`.
   - Nothing calls either today.
   - **Fix:** step 22.
5. **[low] (code) `src/profiles/forms.py:48`: `@transaction.atomic` is untested.**
   - **Problem:** removing it leaves the suite green.
   - **Fix:** step 23.
6. **[low] (code) `src/tags/models.py`: existing tag rows aren't renormalised.**
   - **Problem:** a legacy `"Machine  Learning"` coexists with a new "Machine Learning", and a legacy tag holding an invisible character makes an unchanged re-save fail.
   - **Decision:** no production data exists yet, so the risk is accepted and documented in step 24, with no data migration.
7. **[low] (code) `src/profiles/tests/test_views.py:84-85,187`: the "404 body doesn't contain A's data" checks can't fail.**
   - **Problem:** with `DEBUG` off, the 404 page is generic.
   - **Fix:** step 23 compares a foreign-pk response with a missing-pk response instead.
8. **[low] (code) `src/profiles/tests/test_views.py:106-118`: the AC3 fixture-user test doesn't assert that the user had no profile beforehand.**
   - **Fix:** step 23.
9. **[low] (code) `CLAUDE.md:10`: the Tags bullet misstates what `save()` vs validation does.**
   - **Problem:** also, the `OwnProfileMixin` rule reads as if the mixin were generic.
   - **Fix:** step 24.
10. **[low] (security) `src/tags/models.py:46-48`: keeping the first spelling hints that someone else already created a tag.**
    - **Problem:** e.g. typing "aCmE rEoRg" comes back as "Acme Reorg".
    - **Decision:** accepted for #6, since AC7 chose this behaviour. Reconsider before session tags (#11), e.g. by storing each user's own spelling on the link row. The cap from step 19 limits how many guesses one request can make.
11. **[low] (security) `src/tags/models.py:15`: NFKC runs before the length check.**
    - **Problem:** this is linear and cheap on Linux and macOS. It is a concern on Windows (the CVE-2025-27556 pattern).
    - **Fix:** step 19's `max_length` on the form field bounds the input before NFKC.

### Info (no action this ticket)
- The invisible-character check doesn't catch invisible *letters*: U+3164/U+115F/U+FFA0 Hangul fillers and U+2800 braille blank. Homoglyphs and non-ASCII case remain out of scope. Revisit together with look-alike tags.
- `name` and `cohort` reject NUL (Django's form validator) but not other Cc/Cf characters such as the RTL override. Today only the owner and the admin see them, escaped. Reuse `reject_invisible_characters` once profiles are shown to others.
- The entry-named error repeats the input, escaped. The test for this is added in step 23.
- `GET /profile/` can create the user's own empty profile, which has no impact.
- Sequential profile ids reveal roughly how many users there are. That follows from the user's URL choice.

## Reviewed
commit 30038f7, 2026-10-02
