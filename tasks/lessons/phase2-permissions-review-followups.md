# Lesson: permission-endpoint test backfill — don't pin bad contracts

## What happened

An initial Phase-2 backfill of pytest coverage for three permission
endpoints (`project-user-permissions`, `project-team-permissions`,
`experiment-user-permissions`) was marked complete in
`tasks/todos/api-v2-coverage-backfill.md`. An adversarial review
(recorded in `.cursor/plans/phase_2_permission_tests_review_189489cd.plan.md`)
found:

1. **False matrix-coverage claim.** The author claimed the
   `(level × permission_type)` matrix was "already covered elsewhere
   (`test_cylinder_fleet_api.py`)". It wasn't — `test_cylinder_fleet_api.py`
   doesn't use `parameterized_class`, and no test anywhere in the repo
   hit the three permission endpoints with a level sweep.

2. **Bad contracts pinned rather than fixed.** Two cases were tested
   as-is with "quirky but real" comments rather than filed as bugs:
   - `ValueNotFoundError -> HTTP 404` for a missing request body field.
     Semantic 404 is "resource not found"; missing-field is malformed
     input and should be 400.
   - The team-permission serializer accepted `level=ADMIN`, which the
     DB `CheckConstraint` then rejected with an `IntegrityError` ->
     unhandled HTTP 500. No negative test existed.

3. **Dead inline 400 branches.** Five permission views each carried a
   `if user == perm_data["user"]: return 400` block in PUT and DELETE
   that was unreachable because `_process_request_data` raised
   `NotAuthorizedError(401)` first. Ten branches total, each inviting a
   future maintainer to treat them as the canonical self-target guard.

4. **Assertion hedges.** Things like
   `team.id in team_ids or str(team.id) in team_ids` betrayed that the
   author didn't know the serializer's output type (UUID vs str). Either
   branch passing let a future type change slip silently.

5. **Latent test flake.** `UserFactory.Meta.django_get_or_create =
   ["email"]` + `Faker("email")` can collide when the same test calls
   `UserFactory.create()` twice — the second call returns the first
   user, causing `IntegrityError` on the next `get_or_create` against a
   unique constraint.

## Remedial actions taken in the same branch

- Added `MissingFieldError(status_code=400)` to
  `speleodb/utils/exceptions.py` and migrated the five permission views
  (`user_project_permission.py`, `user_experiment_permission.py`,
  `cylinder_fleet.py`, `sensor_fleet.py`, `surface_network.py`) to raise
  it for missing body fields.
- Tightened
  `TeamRequestWithProjectLevelSerializer.level` in
  `speleodb/api/v2/serializers/request_serializers.py` to
  `choices_no_admin` so `ADMIN` is rejected at the serializer layer
  instead of the DB layer.
- Deleted the 10 unreachable 400 branches across the five views. The
  self-target guard lives once, in `_process_request_data`.
- Rewrote the three Phase-2 test files with:
  - `parameterized_class` matrix coverage over `(level, permission_type)`
    for list-GET and detail-POST on each endpoint.
  - Negative-space tests: missing field (400 now), missing user field,
    empty body, inactive target user (401), invalid level, whitespace
    level, empty-string level, unknown team UUID, malformed team UUID,
    team `level=ADMIN` rejection, anonymous POST/PUT/DELETE,
    non-admin PUT/DELETE (not just POST).
  - Idempotent-DELETE tests: second DELETE returns 404, not 500.
  - Soft-deleted-perm tests: PUT on a soft-deleted perm returns 404,
    not a silent reactivation.
  - Count-aware list tests: assert exact permission count + cross-project
    isolation + soft-deleted exclusion.
  - Audit-trail assertions on reactivation: `deactivated_by` cleared,
    `modified_date` refreshed.
  - `_unique_email()` helper that generates `uuid4`-suffixed emails to
    eliminate `django_get_or_create` email-collision flakes.

## Rules for next time

1. **Don't pin a semantic bug — file it.** If the current behaviour is
   wrong (e.g. 404 for missing field, 500 for a valid request), the
   right move is to fix it in the same branch or open a tracked ticket,
   not to write a test that freezes the wrong contract.

2. **"Covered elsewhere" needs a citation.** If you claim the matrix is
   tested elsewhere, point at the specific file + line where a
   `parameterized_class` or equivalent sweep exercises exactly the
   matrix you're deferring. Otherwise, build it yourself.

3. **Delete dead code in the same branch.** Unreachable branches are
   not "defensible safety nets" — they're traps for the next
   maintainer. If you've just proved the branch is unreachable (by
   writing a test that pins the reachable contract), delete it.

4. **Never hedge assertions with `x in L or str(x) in L`.** Read the
   serializer. Know the output type. If you want type-independence, use
   an explicit conversion (`str(x) in [str(v) for v in L]`) and
   document that you're doing so deliberately.

5. **When a factory has `django_get_or_create` on a faked field, pass an
   explicit unique value.** `_unique_email(prefix)` returning
   `f"{prefix}-{uuid.uuid4()}@test.local"` is cheap and prevents a whole
   class of hard-to-reproduce flakes.

6. **List endpoints need count-aware tests.** "the user appears in the
   list" is too weak — also create noise (other project, soft-deleted,
   unrelated) and assert exact length. Otherwise you catch nothing that
   leaks extra rows into the response.

7. **Test self-target guards on every method that has one.** POST, PUT,
   and DELETE each deserve `test_cannot_target_self`. If only POST is
   tested, a regression in the shared helper that trips only PUT will
   silently ship.

8. **Test idempotency on DELETE.** A second DELETE of the same resource
   must return 404, not 500. This is the cheapest integration test in
   the world and catches the next "refactor that forgot to `is_active=True`
   in the lookup" bug.

9. **Top-level entities are NEVER hard-deleted. Period.** Projects,
   teams, experiments, cylinder fleets, sensor fleets, surface networks,
   and GIS views are all soft-deleted via `.deactivate()` (or the
   project/team pattern of deactivating *children* and leaving the row
   in place for a later cronjob cleanup). The reasons are twofold:
   preserving audit/referential history, and avoiding destructive
   operations on user data behind a single-click button.

   The `DELETE /api/v2/teams/<uuid>/` endpoint originally used
   `team.delete()` (hard-delete), which violated this convention. It
   hit HTTP 500 in production whenever the team had memberships or
   project permissions because the CASCADE-delete tripped a latent
   `transaction.on_commit` / FK-descriptor race in
   `speleodb/surveys/signals.py`. The **correct** fix was to align the
   endpoint with the project-delete convention
   (`speleodb/api/v2/views/project.py::delete`): deactivate all active
   memberships and team project permissions, leave the `SurveyTeam`
   row in place. After that, the signal-race path is no longer reachable
   via the API, and the signals themselves are left untouched —
   minimal-impact.

   Rule: when adding a new DELETE endpoint for a top-level entity,
   default to the soft-delete shape (deactivate children, optionally
   flip `is_active` on the parent). Only introduce a hard-delete if
   there's a specific, documented reason — and if you do, verify every
   signal in the CASCADE graph survives commit-time FK-descriptor
   access (see note below).

10. **Signal sanity for CASCADE delete (informational, not currently
    exercised by the API):** if a future change ever hard-deletes a
    model whose rows cascade to `UserProjectPermission`,
    `TeamProjectPermission`, or `SurveyTeamMembership`, the existing
    handlers in `speleodb/surveys/signals.py` will crash at commit time
    because they dereference FKs (`instance.target`, `instance.team`)
    inside `transaction.on_commit(...)` — by commit time CASCADE has
    already torn the parent row down. Historically this was invisible
    to tests because `django.test.TestCase` rolls back the outer
    transaction and never fires on_commit callbacks. Today the bug is
    not reachable through any API endpoint (all top-level entities
    soft-delete). If you change that, you MUST either:
    - snapshot scalar FK ids synchronously inside the signal body and
      close over Python values in the `on_commit` callback; and/or
    - move the delete-path handler from `post_delete` to `pre_delete`
      so sibling-row queries still return rows; and
    - add a regression test that wraps the request in
      `self.captureOnCommitCallbacks(execute=True)` to actually
      exercise the callback.
