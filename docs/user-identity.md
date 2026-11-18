# Required account names and Git authorship

Every stored user must have a name containing at least one non-whitespace
character. Account creation and profile edits reject missing or blank names;
`NO NAME` is reserved as the repair value for existing unnamed accounts and as
the defensive Git author fallback. It is not an automatic model/database
default. Valid international names and punctuation remain supported. Existing
signup length requirements and API sanitization continue to apply.

## Why validation exists at several boundaries

`blank=False` controls Django validation, not ordinary ORM saves. `null=False`
rejects SQL NULL but permits an empty string. Forms, manager calls, signup and
database writes therefore need an explicit nonblank-name contract.

`speleodb.utils.user_identity` owns the shared nonblank validator and fallback
constant. Its explicit Unicode whitespace pattern avoids different meanings of
`\s` in Python/SQLite and PostgreSQL locales. The user field, manager, and model
save enforce that policy. The model validates only writes that include the name;
unrelated partial saves and saves with a deferred name do not fetch it just for
validation. No full-model validation or additional SQL query is added.

The `users_user_name_nonblank` database check closes paths that bypass model
save, including queryset updates, bulk writes, fixtures, and raw SQL. Existing
NOT NULL enforcement remains. Application validation raises `ValidationError`;
database-only violations raise `IntegrityError`.

Admin creation exposes the required field. Django's standard `createsuperuser`
validates it for interactive prompts, `--name`, and `DJANGO_SUPERUSER_NAME`.
Scripts calling `create_user` or `create_superuser` must pass `name=...`.
`AccountAdapter.save_user` assigns validated signup fields before allauth's
first save and preserves `commit=False`; the later custom signup hook does not
perform a second profile save.

The user serializer validates names again after `SanitizedFieldsMixin` finishes.
HTML-only and other values reduced to an empty string return HTTP 400 with a
name error instead of reaching the database. PATCH requests that omit name
remain valid. Other serializers keep their existing behavior.

## Git compatibility boundary

Git commits use a supervised CLI process to bound hooks and subprocesses. Git
identity formatting can reject a name that remains valid for display; retrying
an invalid identity cannot repair it.

`GitRepo._commit_project` substitutes `NO NAME` for absent/whitespace-only
author names and names made only of characters Git discards from an identity.
This is a Git-only projection: display names are not rewritten to match Git
formatting. Usable names, author email, configured committer, message bytes, and
existing retry/deadline behavior are preserved. The fallback requires no
database or network calls and also protects stale user instances held across a
migration.

Historical Git commits and stored historical author metadata are not rewritten.

## Name repair and database reversal

Migration `users.0009_require_user_name` uses the historical model to update
only blank/whitespace-only names to `NO NAME`, then adds the check constraint.
Its repair value and whitespace pattern are frozen in the migration. This is one
database-side update followed by constraint validation, not per-user saves or
signals. Valid names, emails, permissions, passwords, and verification state are
untouched.

The constraint requires signup to assign a validated name before the first
insert. Application versions that insert unnamed users cannot write under this
schema. Reversing the migration removes the constraint but intentionally retains
repaired names; it cannot recover which blank string a repaired account
previously contained.

When applying this migration to a database still served by old signup code,
quiesce account writes until compatible application processes are running.
Verify that no blank names remain and check signup, admin and CLI account
creation, plus an Ariane upload, before resuming ordinary writes.

## Verification

Run tests only inside the existing application container. Coverage includes
model/manager validation; admin, CLI, headless signup, and sanitized profile
updates; direct and bulk database writes; migration repair and rollback/reapply;
deferred/partial-save query behavior; and real local Git commits/pushes with
preserved authorship. The complete suite uses an isolated PostgreSQL test
database, including real constraint and rollback checks. Configure its
connection explicitly in the test environment; development database contents are
never test fixtures.

A real Ariane regression uses a repaired database user plus a stale unnamed
in-memory user to verify successful upload and correct remote/stored authorship.
It reuses a canonical GitLab allocation and never disables the database check.
Follow [the GitLab test contract](ci-gitlab-testing.md), record audit counts and
cleanup, and run the full Python suite before declaring verification complete.
