# Review: profile-model

## Verdict: PASS

This is the second final review. The first one (commit a919c45) failed by the user's decision. Its medium finding (a race in `get_or_create_by_name`) and its untested design items became plan steps 19–24; see "Earlier review" below.

This round:
- Neither the code reviewer nor the security reviewer found a high or medium issue.
- The race fix was confirmed against a real concurrent insert from a second SQLite connection.
- Every acceptance criterion, AC1 to AC11, has a test that the code reviewer saw fail under a mutation of its behaviour.
- The suite passes (100 tests, also with `--parallel 4 --shuffle`), and `ruff check` and `ruff format --check` are clean.
- The user chose to pass with the low findings recorded (2026-10-02).

## Acceptance criteria
- AC1: covered by `tags.tests.test_apps` and `profiles.tests.test_apps`. PASS
- AC2: covered by `tags.tests.test_models.TagModelTests`: `test_tag_has_a_short_name_and_shows_it`, `test_name_is_stored_trimmed`, `test_blank_or_whitespace_only_name_is_invalid` and `test_a_missing_name_is_invalid_not_a_crash`. PASS
- AC3: covered by `TagModelTests.test_names_are_unique_regardless_of_case` and the five `GetOrCreateByNameTests`, including `test_losing_a_creation_race_returns_the_existing_tag`. PASS
- AC4: covered by `profiles.tests.test_models.ProfileFieldTests.test_profile_has_the_agreed_fields` and `accounts.tests.test_models.UserModelTests.test_custom_user_model_adds_no_fields`. PASS
- AC5: covered by `profiles.tests.test_signals.ProfileAutoCreationTests` (all three tests) and `profiles.tests.test_admin…test_adding_a_user_in_the_admin_creates_exactly_one_profile`. PASS
- AC6: covered by `ProfileTests.test_deleting_the_user_deletes_the_profile`. PASS
- AC7: covered by `ProfileTests.test_shows_the_name_or_else_the_username`. PASS
- AC8: covered by `ProfileTests.test_focus_areas_are_shared_tags`. PASS
- AC9: covered by `tags.tests.test_admin.TagAdminTests`, `UserAdminProfileInlineTests.test_user_change_page_shows_the_profile_inline`, `test_focus_areas_are_picked_with_the_tag_autocomplete` and `test_adding_a_user_in_the_admin_creates_exactly_one_profile`. PASS
- AC10: covered by `profiles.tests.test_migrations…test_users_who_existed_before_get_one_profile`. PASS
- AC11: covered by `accounts.tests.test_models.MigrationsTests`. PASS

## Findings (this round; low, recorded by the user's decision)
1. **[low] (code) `src/tags/tests/test_models.py:72-93`: the race test never checks that its forced lookup miss actually happened.**
   - **Problem:** if the lookup is rewritten (`.get()`, `.exists()`), the test could stop simulating the race without anyone noticing.
   - **Later fix:** `self.assertEqual(missed, [True])` after the block.
2. **[low] (code and security) `src/tags/models.py:29-30`: an `IntegrityError` other than the unique-name one would surface as `Tag.DoesNotExist`.**
   - **Problem:** the original error is kept only as `__context__`. No such constraint exists today.
   - **Later fix:** Django's `get_or_create` pattern: on `DoesNotExist`, re-raise the original `IntegrityError`.
3. **[low] (security) `src/tags/models.py:17-18`: the lookup runs before the input is validated.**
   - **Problem:** a name over SQLite's 50,000-byte `LIKE` pattern limit raises `OperationalError` (a 500) instead of a `ValidationError`.
   - **Later fix:** validate (`full_clean(validate_constraints=False)` or a length check) before the lookup.
4. **[low] (security) `src/tags/models.py`: NUL and control characters aren't rejected in tag names.**
   - **Problem:** `"Python\x00junk"` may match `"Python"`, because SQLite's `LIKE` stops at the NUL.
   - **Later fix:** `ProhibitNullCharactersValidator`, or the normalisation planned for #6.
5. **[low] (code) `src/tags/models.py:5-8` against plan step 20: only `None` gives a `ValidationError`.**
   - **Problem:** other non-strings are coerced (`123` → `"123"`). Form input is always `str`.
6. **[low] (code) `CLAUDE.md:10`: "Trimming and the 50-character limit apply only through `save()`/`full_clean()`" is not quite right.**
   - **Problem:** the length limit applies only in `full_clean()`, because SQLite ignores varchar length.
7. **[low] (code) `CLAUDE.md:9`: "saved through `save()`" should read "created through `save()`".**
   - **Problem:** a user that already exists without a profile and is re-saved gets none.
8. **[low] (code) `README.md:49`: the Layout line still says profiles are "created automatically for every user".**
   - **Problem:** it contradicts the qualified paragraph at `README.md:22`.
9. **[low] (security, process) the #6/#11 guidance must outlive this file.**
   - **Done:** posted as comments on issues #6 and #11 (user decision, 2026-10-02). See below.
10. **[info] (code and security) "safe under concurrent creation" holds for this project's autocommit requests on SQLite.**
    - Inside an outer transaction, a competing SQLite writer gets "database is locked" first.
    - On PostgreSQL (`REPEATABLE READ`, or `UPPER`- vs `LOWER`-based folding), re-check.
11. **[info] (security) the first spelling of a tag is global, user-controlled text.**
    - Templates must keep autoescaping, and must never use `|safe` on tag names.

### Guidance for #6 (profile page) and #11 (sessions), carried forward from the first review
The shared tags are global by design. Tag text one user types is visible to anyone shown the whole tag list. So:
- scope every query from the owner (`request.user.profile.focus_areas`, `Tag.objects.filter(profiles__user=request.user)`)
- never render `tag.profiles` in user views
- don't offer an all-tags choice list or expose the `created` flag
- take the profile from `request.user`, never from a pk in the URL
- use `Profile.objects.get_or_create(user=request.user)`, not a bare `user.profile`
- add a test that user A's data never shows on user B's page
- before users type tags, normalise names: NFKC, reject control and format characters (including NUL), and optionally a `casefold()` key column with the unique constraint on it. This covers look-alike tags (non-ASCII case, NFC/NFD, homoglyphs, zero-width characters) and findings 3 and 4.

### Info (no action, from both rounds)
- The admin inline's permissions are correct: it uses `profiles.*_profile` permissions, has no `user` field and can't be deleted.
- The autocomplete endpoint requires staff and `tags.view_tag`.
- `iexact` escapes `%`, `_` and `\`, and there is no raw SQL.
- The data migration is idempotent and ORM-only: 20,000 users went in one INSERT.
- The settings change is safe.
- Only trusted admins should get `change_tag`/`delete_tag`.

## Earlier review (commit a919c45, verdict FAIL by the user's decision)
Findings 1–9 became plan steps 19–24 and are resolved:
1. **[medium] `get_or_create_by_name` raced:** now race-safe, using a savepoint and recovery from `IntegrityError` (step 19).
2. **`None` names crashed with `AttributeError`** (step 20).
3. **The fixture-load (`raw`) guard was untested** (step 21).
4. **The tag autocomplete was untested** (step 22, which also corrected the plan's assumption about `data-model-name`).
5. **The backfill test checked only `name`; the admin add POST was unchecked** (step 23).
6. **The docs overstated the invariants and the limits on trimming and length** (step 24).

## Reviewed
commit 46ec1aa, 2026-10-02
