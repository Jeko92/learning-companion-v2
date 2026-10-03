# Dashboard: hours per tag and per week
Issue: #19 · Branch: feature/dashboard-hours

## Story
As a logged-in learner, I want my dashboard to show how much time I have logged per tag and per week, so that I can see where my learning time goes and how steady it has been lately.

## Acceptance criteria
- [ ] AC1 The dashboard has an "Hours per tag" section, labelled by its `<h2>` through `aria-labelledby`. It contains a table with a Tag / Time header and one row per tag on the user's sessions. Each row shows the sum of `duration_minutes` of the user's sessions with that tag.
- [ ] AC2 Per-tag rows are ordered by total time, largest first. Ties are ordered by tag name, case-insensitively.
- [ ] AC3 A session with several tags counts its full duration under each of them. The per-tag table has no Total row, and a note under it says that a session with several tags counts under each.
- [ ] AC4 Time from sessions without tags is shown as a final "Untagged" row. The row appears only when the user has untagged time.
- [ ] AC5 The dashboard has an "Hours per week" section, labelled by its `<h2>` through `aria-labelledby`. It contains a table with a Week / Time header and exactly 8 rows: the current week and the 7 weeks before it, newest first. The current week is the one containing `timezone.localdate()`.
- [ ] AC6 Weeks run Monday to Sunday. Each row is labelled "Week of <Monday>", formatted like "Week of Sep 28, 2026". A Sunday session counts in the week that started the Monday before, and a Monday session starts a new week.
- [ ] AC7 Each week row shows the sum of `duration_minutes` of the user's sessions dated in that week. A week without sessions shows "0 min". Sessions dated before the oldest of the 8 weeks, or after the current week, are not counted.
- [ ] AC8 Only the current user's sessions are counted, through `LearningSession.objects.owned_by`. Another user's sessions never change a total, even when they use the same tag. A tag used only by another user never appears.
- [ ] AC9 Times are shown with the existing `duration` format ("45 min", "2 h", "1 h 30 min"), as on the goal page.
- [ ] AC10 A user with no sessions sees "No sessions logged yet." in the per-tag section instead of the table. The per-week table still shows all 8 weeks at "0 min".
- [ ] AC11 Both totals come from ORM aggregation: per tag, `values` + `annotate(Sum("duration_minutes"))`; per week, `TruncWeek("date")` + `Sum`. The dashboard's query count stays fixed as sessions, tags and goals grow. The existing pin moves from 3 to 5 queries: session, user, status counts, per-tag totals, per-week totals.

## Out of scope
- Chart libraries, CSS bars and date-range pickers. Both are plain tables.
- Linking a tag or week to a filtered session list. No such list exists across goals.
- Decimal-hour display. Times use the `duration` format.
- Changing the "Goals by status" section.

## Notes
- Answers to the issue's open questions:
  - **Per-week range:** the last 8 weeks, the current week included. Weeks without sessions show 0.
  - **Display:** tables only, in the style of the Goals by status table.
- Other answers from the interview:
  - Untagged time gets an "Untagged" row.
  - The per-tag table has no Total row, because multi-tag sessions count under each tag.
  - Times use the existing `duration` filter rather than decimal hours. The handout's "hours" is met by the per-hour formatting ("2 h", "1 h 30 min"). Session-model notes said "the dashboard divides by 60", but the app has always shown minute totals through `duration`, so the dashboard stays consistent with that.
- Defaults chosen without asking, open to change at approval:
  - Per-tag rows are ordered by time, largest first, with ties by name case-insensitively. `Tag`'s own ordering is case-sensitive.
  - The empty-state wording is "No sessions logged yet.".
  - The week label uses the "Sep 28, 2026" format.
- **Constraints:**
  - `LearningSession` has `Meta.ordering = ("-date", "-created_at", "-id")`. `Meta.ordering` stays out of GROUP BY, but any explicit `order_by()` on an incoming queryset splits the groups (see `work/dashboard-status/review.md`).
  - A user's tags are reached only through their sessions (`owned_by`), never through an unscoped `tag.sessions`.
  - `TruncWeek` on the `DateField` gives Monday-start weeks. On SQLite it computes `date - weekday()`.
  - `date` rejects future dates only through `full_clean()`, so AC7 has to exclude them in the query.
- Updating `CLAUDE.md` (the dashboard bullet) and `README.md` is part of this ticket.
- Handout: `instructions/challenge.md` → "Learning Companion - Dashboard and reporting". Depends on #12 and #18, both done.
- **Approval:** the user approved the acceptance criteria (AC1–AC11) on 2026-10-03, including the defaults above.
