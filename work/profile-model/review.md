# Review: profile-model

## Verdict: FAIL

The two reviewers (code and security) found no high-severity issues. The suite is green: 95 tests, also run with `--parallel`, `--reverse` and `--shuffle`. Lint is clean. Every acceptance criterion has a test that the code reviewer saw fail when its behaviour was removed.

The review still fails, on the user's decision (2026-10-02): the medium finding 1 and the untested design items (findings 3–6) are fixed before the PR. They became plan steps 19–24.

## Acceptance criteria
- AC1: covered by `tags.tests.test_apps` and `profiles.tests.test_apps`. PASS
- AC2: covered by `tags.tests.test_models.TagModelTests`: `test_tag_has_a_short_name_and_shows_it`, `test_name_is_stored_trimmed` and `test_blank_or_whitespace_only_name_is_invalid`. PASS
- AC3: covered by `TagModelTests.test_names_are_unique_regardless_of_case` and the three `GetOrCreateByNameTests`. PASS, but see finding 1: it isn't race-safe.
- AC4: covered by `profiles.tests.test_models.ProfileFieldTests.test_profile_has_the_agreed_fields` and `accounts.tests.test_models.UserModelTests.test_custom_user_model_adds_no_fields`. PASS
- AC5: covered by `profiles.tests.test_signals.ProfileAutoCreationTests` (both tests) and `profiles.tests.test_admin…test_adding_a_user_in_the_admin_creates_exactly_one_profile`. PASS
- AC6: covered by `ProfileTests.test_deleting_the_user_deletes_the_profile`. PASS
- AC7: covered by `ProfileTests.test_shows_the_name_or_else_the_username`. PASS
- AC8: covered by `ProfileTests.test_focus_areas_are_shared_tags`. PASS
- AC9: covered by `tags.tests.test_admin.TagAdminTests` and the two `UserAdminProfileInlineTests`. PASS. Autocomplete is untested; see finding 4.
- AC10: covered by `profiles.tests.test_migrations…test_users_who_existed_before_get_one_profile`. PASS. "Empty" is checked only for `name`; see finding 5.
- AC11: covered by `accounts.tests.test_models.MigrationsTests`. PASS

## Findings
1. **[medium] (code and security) `src/tags/models.py:11-16`: `get_or_create_by_name` isn't safe when two requests create the same tag at once.**
   - **Problem:** it does a lookup, then `full_clean()`, then `save()`. If another request inserts the same name in the gap, the caller gets an error instead of the existing tag:
     - a `ValidationError` ("A tag with this name already exists.") if the insert lands between the lookup and `full_clean`
     - an `IntegrityError` if it lands between `full_clean` and `save`, which also breaks an outer `atomic()`

     #6 and #11 will send every typed tag through this method.
   - **Fix:** step 19.
2. **[low] (code and security) `src/tags/models.py:43,48`: `.strip()` is called on any value.**
   - **Problem:** `Tag(name=None).full_clean()` and `get_or_create_by_name(None)` raise `AttributeError`, where a `ValidationError` is expected.
   - **Fix:** step 20.
3. **[low] (code) `src/profiles/signals.py:16`: the `not raw` guard (fixture loads create no profile) is untested.**
   - **Problem:** changing it to `if created:` leaves the suite green.
   - **Fix:** step 21.
4. **[low] (code) `src/profiles/admin.py:12`: `autocomplete_fields` is untested.**
   - **Problem:** removing it leaves the suite green.
   - **Fix:** step 22.
5. **[low] (code) `src/profiles/tests/test_migrations.py:38`: the backfill test checks only `name == ""`, not that the profile is fully empty.**
   - **Fix:** step 23.
6. **[low] (code) `src/profiles/tests/test_admin.py:50`: the add-user POST response is unchecked.**
   - **Problem:** a rejected form would surface as `DoesNotExist` rather than as a clear failure.
   - **Fix:** step 23.
7. **[low] (code) `src/tags/models.py:46-48`: trimming happens only in `save()`.**
   - **Problem:** `QuerySet.update()` and `bulk_create()` can store untrimmed names, and `" python"` then gets past the `Lower` constraint.
   - **Fix:** step 24 documents it. `get_or_create_by_name` is the creation path.
8. **[low] (code) `CLAUDE.md:9`, `README.md`: "every user has exactly one profile" is stronger than the code.**
   - **Problem:** `bulk_create` and raw fixture loads skip the signal.
   - **Fix:** step 24.
9. **[low] (code) `CLAUDE.md` and `README.md` additions went beyond plan step 18.**
   - **Detail:** the RUF012 and `TransactionTestCase` rules, and the README profile paragraph. They are accurate.
   - **Fix:** step 24 records them.
10. **[low] (security) `src/tags/models.py`: look-alike tags are still possible.**
    - **Problem:** none of these are caught:
      - non-ASCII case: "PYTHÖN" and "pythön"
      - NFC/NFD spellings of the same text
      - homoglyphs such as a Cyrillic "у"
      - zero-width characters, which `strip()` keeps

      This is harmless while only the admin creates tags. It matters once users type tags in (#6 and #11), because duplicates split the #19 per-tag totals.
    - **Fix:** not done in this ticket. Recommended for #6: NFKC normalisation, rejecting control and format characters, and optionally a `casefold()` key column with the unique constraint on it.
11. **[low] (security) `src/tags/models.py`: `max_length` is checked only in validation.**
    - **Problem:** SQLite doesn't enforce it, so direct `create()` calls can store longer names.
    - **Fix:** documented under step 24. `get_or_create_by_name` is the only creation path #6 and #11 should use.

### Guidance for #6 (profile page) and #11 (sessions), from the security review
The shared tags are global by design. Tag text one user types is visible to anyone shown the whole tag list. So:
- scope every query from the owner (`request.user.profile.focus_areas`, `Tag.objects.filter(profiles__user=request.user)`)
- never render `tag.profiles` in user views
- don't offer an all-tags choice list or expose the `created` flag
- take the profile from `request.user`, never from a pk in the URL
- use `Profile.objects.get_or_create(user=request.user)`, not a bare `user.profile`, because a user loaded from a fixture has no profile
- add a test that user A's data never shows on user B's page

### Info (no action)
- The admin inline's permissions are correct: it uses `profiles.*_profile` permissions, has no `user` field and can't be deleted.
- The autocomplete endpoint requires staff and `tags.view_tag`.
- `iexact` escapes `%`, `_` and `\`, and there is no raw SQL.
- The data migration is idempotent: 20,000 users went in one INSERT, and a reverse followed by a re-apply is safe.
- The settings change is safe.
- Only trusted admins should get `change_tag`/`delete_tag`, since a tag is shared by every user.

## Reviewed
commit a919c45, 2026-10-02
