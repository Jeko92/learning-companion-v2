# Review: profile-page

## Verdict: PASS

This is the second final review. The first one (commit 30038f7) failed on:
- one high finding: the focus-area input was unbounded, so one save could lock the database
- two medium findings: full-width commas weren't treated as separators, and AC7's case-merge rule had no test that could fail

Plan steps 19–24 fixed them and added AC13.

This round was reviewed under the new ticket-scope rules (commits dfe47ef and 86c8687). The code reviewer covered only the fix steps (`5bca3e6..HEAD`), and the security reviewer confirmed its earlier findings. Results:
- **No high or medium findings.**
- All targeted earlier findings are resolved, each confirmed by a mutation that turns its test red.
- The suite passes (134 tests); `ruff check`, `ruff format --check` and `makemigrations --check` are clean.

## Acceptance criteria
- AC1: covered by `ProfileDetailTests.test_your_own_profile_page_is_served`, `MyProfileTests.test_sends_you_to_your_own_profile` and `ProfileEditTests.test_edit_page_renders_your_profile_in_a_form`. PASS
- AC2: covered by the anonymous-visitor tests in `ProfileDetailTests`, `MyProfileTests` and `ProfileEditTests`, the last for both GET and POST. PASS
- AC3: covered by `MyProfileTests.test_creates_a_missing_profile_first`, which now checks there's no profile before and exactly one after. PASS
- AC4: covered by `ProfileDetailTests` (the page is served; values or placeholders) and `ProfileEditTests.test_detail_page_links_to_the_edit_page`. PASS
- AC5: covered by `ProfileDetailTests.test_another_users_profile_or_a_missing_one_is_not_found` and `ProfileEditTests.test_another_user_cannot_see_or_change_your_profile`. Both check the 404 status and that the 404 body is identical to the one for a missing id. PASS
- AC6: covered by `ProfileEditTests.test_edit_page_renders_your_profile_in_a_form` and `ProfileEditCsrfTests`. PASS
- AC7: covered by `ProfileEditTests.test_a_valid_save_stores_trimmed_values_and_redirects`, three `FocusAreasInputTests` tests (comma-separated text, full-width commas, non-ASCII case merge) and three `ProfileFormTests` tests. PASS
- AC8: covered by `ProfileEditTests.test_invalid_input_rerenders_the_form_and_saves_nothing` and `FocusAreasInputTests.test_an_invisible_character_is_a_field_error_and_saves_nothing`. PASS
- AC9: covered by the six `tags.tests.test_models.NameNormalisationTests`, including the new commas test. PASS
- AC10: covered by `ProfilePrivacyTests`. PASS
- AC11: covered by `accounts.tests.test_nav…test_logged_in_nav_links_the_username_to_the_profile_and_has_logout`. PASS
- AC12: covered by `ProfileEscapingTests`, now also for a rejected entry echoed in an error. PASS
- AC13: covered by `FocusAreasInputTests.test_focus_area_input_is_bounded_before_any_database_work` and `test_twenty_focus_areas_are_allowed`. PASS. The limits (1,000 characters, 20 entries) were proposed in review; the user then went on to implementation.

## Findings (this round; all low, recorded)
1. **[low] (code) `src/profiles/tests/test_forms.py:54`: AC13's "distinct" isn't pinned.**
   - **Problem:** counting raw entries instead of de-duplicated names would survive the tests.
   - **Later fix:** 20 distinct entries plus one case-variant duplicate must be accepted.
2. **[low] (code) `src/profiles/tests/test_forms.py:54`: "before any database work" isn't asserted.**
   - **Problem:** a lookup added inside `clean_focus_areas` would survive the tests.
   - **Later fix:** `assertNumQueries(0)` around `form.is_valid()` with 21 entries. The reviewer verified this passes today.
3. **[low] (code and security) `src/profiles/forms.py:70-77`: the deferred `save_m2m()` path after `save(commit=False)` isn't atomic.**
   - **Problem:** a failure partway through leaves orphan tags. Nothing calls this path today.
   - **Later fix:** wrap the `_save_m2m` body in `transaction.atomic()`.
4. **[low] (code) `src/profiles/tests/test_forms.py:113-124`: the `commit=False` test checks only the link rows.**
   - **Problem:** it doesn't check that no tag is created before `save_m2m()`.
5. **[low] (code) `src/profiles/tests/test_forms.py:85-91`: only U+FF0C is pinned.**
   - **Problem:** U+FE50 and U+FE10 aren't tested.
6. **[low] (code) `CLAUDE.md:9`: "A profile takes at most 20 focus areas" overclaims.**
   - **Problem:** the cap lives in `ProfileForm` only. Staff can exceed it through the admin inline, and that user then can't re-save their profile unchanged.
7. **[low] (security) `src/tags/models.py`: tag-table growth across many requests.**
   - **Problem:** each save adds at most 20 tags, but there's no rate limit and no cleanup. `name__iexact` (`LIKE`) can't use the `Lower("name")` index.
   - **Before #11:** look tags up with `Lower(...)`, so the expression index is used, and consider rate limiting or cleaning up orphaned tags.

### Accepted earlier (carried forward)
- **First spelling wins:** this hints that someone else already created the tag (e.g. "aCmE rEoRg" comes back as "Acme Reorg"). Accepted for #6; reconsider before session tags (#11).
- **Look-alike tags:** homoglyphs, non-ASCII case, Hangul fillers and the U+2800 braille blank are still possible. Out of scope; revisit together.
- **Name and cohort characters:** these reject NUL but not other control or format characters. Reuse `reject_invisible_characters` once profiles are shown to others.
- **Legacy tag rows:** rows from before this ticket aren't renormalised, and there's no data migration (no production data). Recorded in `CLAUDE.md`.

### Info (no action)
- **Error echo:** rejected entries are shown in their NFKC form, e.g. "ＰＹＴＨＯＮ" appears as "PYTHON".
- **Other commas:** U+3001 (、) and U+060C don't separate entries. NFKC doesn't map them, and the round trip is stable.
- **Error order:** when the input has both invalid entries and too many entries, the count error only shows on the next submit.
- **404 comparisons:** they would need adjusting if a future `404.html` renders the request path.
- **Ids in URLs:** sequential profile ids reveal roughly how many users exist. That follows from the URL design the user chose.

## Earlier review (commit 30038f7, verdict FAIL)
These were fixed by steps 19–24:
- **[high]** The focus-area input was unbounded. Step 19 added AC13 (1,000 characters, 20 entries, checked before any database work).
- **[medium]** Full-width commas didn't separate entries. Step 20 applies NFKC to the whole text before splitting and adds the `reject_commas` validator (`tags/0004`).
- **[medium]** The non-ASCII case merge had no test that could fail. Step 21 added one.
- **[low]** Step 22 fixed the form's `commit=False` handling and the unbound form.
- **[low]** Step 23 added tests for atomicity, the 404 bodies, the fixture precondition and the escaped error.
- **[low]** Step 24 corrected `CLAUDE.md`.

## Reviewed
commit 86c8687 (source as of a0ab545), 2026-10-02
