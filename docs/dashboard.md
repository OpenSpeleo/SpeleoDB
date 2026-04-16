# Dashboard

## Feature Intent

The dashboard is the authenticated landing page for SpeleoDB. When a user
logs in (or navigates to `/private/`), they see an activity overview instead
of a profile editing form. The goal is to give users immediate insight into
their survey work: project counts, commit activity, contribution patterns,
and recent team activity.

The previous profile editing form is now available at `/private/profile/`
(URL name `private:user_profile`), accessible via the "Profile" sidebar
item and the header user dropdown.

## Metrics Displayed

| Metric | Source | Query |
|--------|--------|-------|
| Total Projects | `user.permissions` | Count of accessible projects (best permission per project) |
| Total Teams | `user.teams` | Active team memberships |
| Your Commits | `ProjectCommit` | `author_email=user.email` on accessible projects |
| Stations Created | `SubSurfaceStation` | `created_by=user.email` |
| Landmarks | `user.landmarks` | FK-based count |
| GPS Tracks | `user.gps_tracks` | FK-based count |
| Projects by Level | `user.permissions` | Breakdown by ADMIN / READ_AND_WRITE / READ_ONLY |
| Commits Over Time | `ProjectCommit` | TruncMonth aggregation, 12-month window, total vs user |
| Contribution Calendar | `ProjectCommit` | Raw per-commit ISO timestamps for user, last 365 days (client groups by local date) |
| Recent Activity | `ProjectCommit` | Last 15 commits across all accessible projects |

## API Endpoint

```
GET /api/v2/user/dashboard-stats/
Authorization: Token <token>
```

Returns a single JSON response with all dashboard data. See
`speleodb/api/v2/views/user_dashboard.py` for the response schema.

## Architecture

```
Login → /private/ → DashboardView → pages/dashboard.html
                                          ↓
                                    jQuery AJAX GET
                                          ↓
                              /api/v2/user/dashboard-stats/
                                          ↓
                                  UserDashboardStatsView
                                   (pure ORM queries)
```

The old profile page lives at:
```
/private/profile/ → ProfileView → pages/user/dashboard.html
```

## Performance

- **Single API call** fetches all dashboard data — no N+1 queries.
- **All queries are ORM-only** — no git filesystem access, no external API calls.
- `ProjectCommit` has a composite index on `(project, authored_date)` which
  makes time-range queries efficient.
- Contribution calendar returns one ISO timestamp per commit (not per day).
  For most users this is well under 1,000 entries per year.
- Chart.js is loaded from CDN with caching, no impact on initial HTML paint.
- Stat card numbers use CSS skeleton loading (animated placeholders) to
  prevent layout jitter while the API call is in flight.

## Frontend

- **Chart.js 4.x** via cdnjs CDN for line and doughnut charts.
- **Contribution heatmap** is a `<table>` with `table-layout: fixed`
  (no library), GitHub-style with emerald color scale.
- **Activity feed** uses `escapeHtml` for all user/API data to prevent XSS.
- Template extends `base_private.html` directly (not the settings layout).

## Testing

Three test files cover the dashboard exhaustively:

| File | Scope | Tests |
|------|-------|-------|
| `speleodb/api/v2/tests/test_user_dashboard_stats.py` | Backend API | ~50 tests: auth, empty state, summary counts, projects-by-level, commits-over-time, contribution calendar, recent activity, edge cases |
| `frontend_private/tests/test_dashboard_views.py` | Django views + templates | ~35 tests: page access, template structure, profile page, URL routing, sidebar navigation, responsive CSS |
| `frontend_private/static/private/js/tests/dashboard.test.js` | JS unit tests | ~25 tests: heatmap rendering, stat cards, activity feed XSS, time formatting, level thresholds |

## Adding New Metrics

1. Add the query to `UserDashboardStatsView._build_summary()` in the API view.
2. Add a stat card in `pages/dashboard.html` with a unique `id`.
3. Add the ID to the `populateStatCards()` function in the inline JS.
4. Add corresponding tests in both the API and frontend test files.
