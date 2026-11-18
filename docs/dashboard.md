# Dashboard

## Feature Intent

The dashboard is the authenticated landing page for SpeleoDB. When a user logs
in (or navigates to `/private/`), they see an activity overview instead of a
profile editing form. The goal is to give users immediate insight into their
survey work: project counts, commit activity, contribution patterns, and recent
team activity.

The previous profile editing form is now available at `/private/profile/` (URL
name `private:user_profile`), accessible via the "Profile" sidebar item and the
header user dropdown.

## Dashboard Data

| Metric                | Source                                   | Query                                                                                        |
| --------------------- | ---------------------------------------- | -------------------------------------------------------------------------------------------- |
| Total Projects        | `user.permissions`                       | Count of accessible projects (best permission per project)                                   |
| Total Teams           | `user.teams`                             | Active team memberships                                                                      |
| Your Commits          | `ProjectCommit`                          | `author_email=user.email` on accessible projects                                             |
| Stations Created      | `SubSurfaceStation`                      | `created_by=user.email`                                                                      |
| Landmarks             | User's personal `LandmarkCollection`     | Collection-scoped count                                                                      |
| GPS Tracks            | `user.gps_tracks.filter(is_active=True)` | Active tracks created by the user; shared-only tracks are intentionally excluded             |
| Projects by Level     | `user.permissions`                       | Breakdown by ADMIN / READ_AND_WRITE / READ_ONLY                                              |
| Commits Over Time     | `ProjectCommit`                          | TruncMonth aggregation in Django's configured local timezone, 12-month window, total vs user |
| Contribution Calendar | `ProjectCommit`                          | Raw per-commit ISO timestamps for user, last 365 days (client groups by local date)          |
| Recent Activity       | `ProjectCommit`                          | Last 15 commits across all accessible projects                                               |

The top row displays three compact cards: Survey Projects links to My Survey
Projects (`private:projects`), Teams links to My Teams (`private:teams`), and
Your Contributions is informational. The row uses a full-width auto-fitting grid
with equal-width cards, wrapping them as space narrows without increasing card
height. Card padding and metric values retain their existing responsive sizing.
Titles sit beside their icons with bright, semibold text. Survey Projects and
Teams use the same icon shapes as their sidebar destinations. All three cards
highlight with an indigo background, bright border, and glow on hover; linked
cards also show this highlight on keyboard focus. All three top action buttons
share the same hover and keyboard focus styles and transition timing. The View
All Projects and Open Survey Map quick actions use the same icon shapes as their
sidebar destinations, My Survey Projects and GIS Survey Map.

The three header quick actions are hidden below the `sm` breakpoint to keep the
mobile dashboard compact. They remain visible on larger screens.

Stations, landmarks, and GPS track counts remain available in the API response
but are not displayed as dashboard cards.

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

The monthly window, response labels, and `TruncMonth` aggregation use Django's
configured local timezone consistently. The view starts from
`timezone.localtime(timezone.now())` and keys both totals and user-authored
counts by `YYYY-MM`; a UTC first-of-month commit can belong to the previous
local month. Regression fixtures anchor commits within explicit local months
rather than subtracting a few days from today, so the total/user split remains
stable on the first days of a month.

## Performance

- **Single API call** fetches all dashboard data — no N+1 queries.
- **All queries are ORM-only** — no git filesystem access, no external API
  calls.
- `ProjectCommit` has a composite index on `(project, authored_date)` which
  makes time-range queries efficient.
- Contribution calendar returns one ISO timestamp per commit (not per day). For
  most users this is well under 1,000 entries per year.
- Chart.js is loaded from CDN with caching, no impact on initial HTML paint.
- Stat card numbers use CSS skeleton loading (animated placeholders) to prevent
  layout jitter while the API call is in flight.

## Frontend

- **Chart.js 4.x** via cdnjs CDN for line and doughnut charts.
- **Contribution heatmap** is a `<table>` with `table-layout: fixed` (no
  library), GitHub-style with emerald color scale.
- **Activity feed** uses `escapeHtml` for all user/API data to prevent XSS.
- Template extends `base_private.html` directly (not the settings layout).

## Testing

Template checks follow the utility-based layout: all three activity avatar
placeholders must be square, fully rounded skeletons, and each chart canvas must
sit directly inside a relatively positioned, fixed-height container. Assert the
current classes rather than historical inline styles; this preserves coverage
when formatting changes without adding runtime work.

The backend, template, helper and controller suites cover the dashboard:

| File                                                         | Scope                    | Tests                                                                                                                                  |
| ------------------------------------------------------------ | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| `speleodb/api/v2/tests/test_user_dashboard_stats.py`         | Backend API              | ~50 tests: auth, empty state, summary counts, projects-by-level, commits-over-time, contribution calendar, recent activity, edge cases |
| `frontend_private/tests/test_dashboard_views.py`             | Django views + templates | ~35 tests: page access, template structure, profile page, URL routing, sidebar navigation, responsive CSS                              |
| `frontend_private/static/private/ts/tests/dashboard.test.ts` | JS unit tests            | ~25 tests: heatmap rendering, stat cards, activity feed XSS, time formatting, level thresholds                                         |

## Adding New Metrics

1. Add the query to `UserDashboardStatsView._build_summary()` in the API view.
2. Add a stat card in `pages/dashboard.html` with a unique `id`.
3. Add the ID to `populateStatCards()` in the registered Vite controller
   `frontend_common/controllers/dashboard.ts`.
4. Add corresponding tests in both the API and frontend test files.

## Typed helper ownership

`frontend_private/static/private/ts/dashboard-helpers.ts` owns the pure display,
calendar, palette, and chart-configuration helpers. Dashboard records and chart
tuples live in `ts-types/domain/dashboard.ts`; they do not add runtime
dependencies or change the controller's request flow. Local date grouping and
locale number formatting remain browser-owned. The exported avatar palette
remains mutable, including the existing undefined color result if a caller
empties it.

`tests/dashboard.test.ts` exercises the real helpers and drives the dashboard
controller through its AJAX success callback for every stat-card and activity
case. The fixture supplies jQuery and finite URL stubs; it contains no duplicate
rendering implementation. This catches changes in real date grouping, links,
escaping and empty states. Chart and heatmap composition remain covered by the
controller initialization suite. Literal edge characterization covers palette
identity, untrimmed single-name initials, and invalid timestamp grouping. Strict
checking uses erased assertions at the existing indexed/backend boundaries
rather than adding validation or fallback behavior. This translation adds no
per-item work.

The typed controller keeps the immediate AJAX request, optional Chart global,
calendar layout and partial rendering after missing-DOM failures. Its direct
initialization suite exercises those boundaries and repeated initialization with
the real jQuery runtime. Chart declarations describe only the existing
constructor and configuration use; no Chart runtime package is bundled.

## Project software counts

Project counts by software include Stalagmight through the existing permission-
scoped database aggregation. The chart references `PROJECT_TYPE_COLORS` in
`speleodb/surveys/templatetags/project_types.py`, the same mapping used for
software badges. The `get_project_type_colors` tag renders hidden swatches using
the canonical badge classes; the controller reads their computed background
colors and passes them to `buildProjectsChartConfig`. No software palette is
maintained in JavaScript. Unknown software uses the canonical Other swatch. See
[project capabilities](project-formats.md) for the software choice contract.

## Fundraiser invitation

The dashboard can show a date-controlled fundraiser invitation and support card.
Account-level dismissal suppresses the invitation for seven days from the latest
dismissal, including after rescheduling. It returns only during the active
campaign dates. See [donation campaign](donation-campaign.md) for the
presentation and persistence contract.
