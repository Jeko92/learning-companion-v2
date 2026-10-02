# Review: goal-model

## Verdict: PASS

This was a first review, run under the new reviewer rules: ticket scope, diff-first reading, and terse reports, with the code reviewer on a faster model. Results:
- Neither reviewer found a high or medium issue.
- The suite passes (148 tests), and `ruff check`, `ruff format --check` and `makemigrations --check` are clean.

## Acceptance criteria
- AC1: covered by `goals.tests.test_apps.InstalledAppsTests.test_goals_app_is_installed`. PASS
- AC2: covered by `goals.tests.test_models.GoalFieldTests.test_goal_has_the_agreed_fields` and `accounts.tests.test_models.UserModelTests.test_custom_user_model_adds_no_fields`. PASS
- AC3: covered by `GoalStatusTests`: `test_status_is_planned_in_progress_or_done`, `test_any_other_status_is_rejected` (validation and the database constraint) and `test_every_status_value_passes_the_database_constraint`. PASS
- AC4: covered by `GoalTitleTests` (`test_title_is_stored_trimmed` and `test_title_is_required_and_at_most_200_characters`). PASS
- AC5: covered by `GoalFieldTests.test_description_is_optional`. PASS
- AC6: covered by `GoalTimestampTests.test_created_at_is_set_once_and_updated_at_on_every_save`. PASS
- AC7: covered by `GoalOrderingTests.test_goals_are_newest_first_with_ties_broken_by_id`. PASS
- AC8: covered by `GoalStrTests.test_shows_its_title`. PASS
- AC9: covered by `GoalOwnershipTests.test_goals_belong_to_their_owner_and_go_with_them`. PASS
- AC10: covered by `goals.tests.test_admin.GoalAdminTests` (registration and changelist). PASS
- AC11: covered by `accounts.tests.test_models.MigrationsTests` (one `goals/0001_initial`). PASS

## Findings (none blocking)
1. **[low] (code) `src/goals/models.py` `Meta.constraints`: the `CheckConstraint` lists the status values literally.**
   - **Problem:** the consistency test catches a value *added* to `Goal.Status` but not one *removed*. A retired value would still pass the database.
   - **Later fix:** assert that the constraint's allowed set equals `set(Goal.Status.values)`.
2. **[low] (code) `src/goals/models.py` `strip()`: the module-level helper has a generic public name.**
   - **Later fix:** rename it `_strip`.
3. **[info] (security) `src/goals/models.py` `owner`, for #8: `owner` is an editable FK.**
   - **Problem:** a goal form with `fields="__all__"` or `owner` would allow mass assignment, i.e. creating or moving goals for another user.
   - **Recommendation:** in #8, leave `owner` out of the form, set it from `request.user`, and test that a posted `owner` is ignored.
4. **[info] (security) `src/goals/models.py` `description`, for #8: the `TextField` has no length limit, and SQLite doesn't enforce one.**
   - **Recommendation:** cap it in #8's form, or on the model. `title`'s 200-character limit also holds only through forms and `full_clean`.
5. **[info] (security) `src/goals/admin.py`: the owner field on the admin add/change form is a select listing every username.**
   - **Problem:** a staff user with only goal permissions can see all accounts.
   - **Recommendation:** `raw_id_fields = ("owner",)`, or `autocomplete_fields`.

Noted during implementation: on create, `created_at` and `updated_at` differ by microseconds. Don't use their equality to mean "never edited".

## Reviewed
commit fa48733, 2026-10-02
