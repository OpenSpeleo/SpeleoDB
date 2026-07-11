# Dashboard Commits Over Time Total

## Plan

- [x] Inspect the failing test fixture and expected dashboard contract.
- [x] Reproduce/check the failing `commits_over_time` test locally.
- [x] Identify why `total` can collapse to the user-authored count.
- [x] Apply the smallest code/test/doc change that fixes the root cause.
- [x] Run focused verification and record the result.

## Review

The dashboard total/user split was correct, but the test fixture was date-flaky:
the two non-user "current month" commits used `now - 2 days`, which belongs to
the previous month when the suite runs on day 2 of a month.

While making the fixture deterministic, the API exposed a timezone boundary bug:
a commit at `YYYY-MM-01T00:00Z` grouped into the previous month under Django's
`America/New_York` timezone while response labels were generated from raw UTC
`timezone.now()`. The fix makes the 12-month window and labels use
`timezone.localtime()` consistently and keys aggregation results by `YYYY-MM`.

Verification:

- `uv run pytest speleodb/api/v2/tests/test_user_dashboard_stats.py -q`
- `uv run ruff check speleodb/api/v2/views/user_dashboard.py speleodb/api/v2/tests/test_user_dashboard_stats.py`
- `uv run mypy speleodb/api/v2/views/user_dashboard.py`
