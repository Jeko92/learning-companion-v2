# Review: resource-model
## Verdict: PASS

Full suite green (311 tests), `ruff check` and `ruff format --check` clean, `makemigrations --check` reports no changes.
- Code review: 0 high, 0 medium, 2 low. 6 mutations: the 5 real changes were all caught; the sixth, model-only drift, is caught by `makemigrations --check`, which passes.
- Security review: 0 high, 0 medium, 0 low, 2 info.

## Acceptance criteria

Test classes are in `resources/tests/test_models.py` unless noted.

- AC1 belongs to one goal, cascade on goal and user delete — covered by `ResourceGoalTests` (3 tests) — PASS
- AC2 `owned_by(user)`, chainable, no leaks — covered by `ResourceOwnedByTests` — PASS
- AC3 URL: http(s) only (including an upper-case scheme), 2,048 maximum, trimmed, one error per bad URL — covered by `ResourceUrlTests.test_the_url_field_holds_long_urls`, `test_http_and_https_urls_are_accepted`, `test_other_schemes_and_non_urls_are_rejected_once`, `test_a_url_over_2048_characters_is_rejected`, `test_the_url_is_stored_trimmed` — PASS
- AC4 database refuses non-http(s) URLs via `update()` — covered by `ResourceUrlTests.test_the_database_only_takes_http_and_https_urls` — PASS
- AC5 title required, 200 maximum, trimmed — covered by `ResourceTitleTests` (4 tests) — PASS
- AC6 type choices, default article, unknown rejected — covered by `ResourceTypeTests.test_the_types_are_article_video_repo_and_doc`, `test_a_new_resource_is_an_article`, `test_an_unknown_type_is_rejected` — PASS
- AC7 database refuses unknown types, every enum value accepted — covered by `ResourceTypeTests.test_the_database_only_takes_known_types` — PASS
- AC8 one URL per goal (validation message and `IntegrityError`), allowed on other goals — covered by `ResourceUniquenessTests` (3 tests) — PASS
- AC9 timestamps, newest first with id tie-break — covered by `ResourceTimestampTests` — PASS
- AC10 `str()` is the title — covered by `ResourceStrTests` — PASS
- AC11 admin columns, filter, search, goal autocomplete, changelist and add page — covered by `resources/tests/test_admin.py` `ResourceAdminTests` — PASS
- AC12 app installed, migration generated, nothing pending — covered by `resources/tests/test_apps.py` `InstalledAppsTests`, `accounts/tests/test_models.py` `MigrationsTests`, and `makemigrations --check` (run here) — PASS
- AC13 docs — covered by the commit `docs(resource-model): document the resources app and Resource model` (`CLAUDE.md` Resources bullet and Layout entry, `README.md` app list), checked by reading it — PASS

## Findings

None of these block the verdict. They are recorded here, and the #14 items should go into `resource-attach`'s refinement and plan.

- [low] `src/resources/models.py` `HttpURLField`: a ModelForm uses `forms.URLField`, whose own validator still allows ftp/ftps. The model validator still rejects ftp in `_post_clean`, once, so nothing gets stored. — Recommendation for #14: add a form-level test that pins the ftp rejection, or override `HttpURLField.formfield()` to use an http(s)-only form validator.
- [low] `src/resources/tests/test_models.py`: there is no test for `title=None` / `url=None` going through `trim()` (the non-string branch of `strip`). `full_clean()` should report them as required rather than crash. — Recommendation: add `None` subtests in a follow-up, or in #14's model-touching step.
- [info] `src/resources/models.py` `UniqueConstraint(goal, url)`: `full_clean()` skips it when `goal` is excluded, so a #14 ModelForm without a `goal` field would turn a duplicate POST into an `IntegrityError` (a 500). — #14 must check duplicates itself (set the goal on the instance and call `validate_constraints()`, or check in the form's `clean()`) and test a duplicate POST. This is already documented in `CLAUDE.md`.
- [info] #14 rendering: keep `href="{{ resource.url }}"` autoescaped (never `|safe`), add `rel="noopener noreferrer"` with `target="_blank"`, and look resources and goals up only through `owned_by`.

## Reviewed
commit 362ccca, 2026-10-03
