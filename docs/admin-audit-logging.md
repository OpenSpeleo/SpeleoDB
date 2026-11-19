# Administrator audit history

## Intent and ownership

`speleodb.users.models.LogEntry` records explicit administrator changes and task
requests. It answers who requested or changed what, and when. It is separate
from Celery `TaskResult`, which records execution progress, results and original
failures, and from account authentication events and station log entries.

The audit has no expiration or maximum row count. Administrator email, target
model label, object ID and description are snapshots, without user or target
foreign keys. Deleting an account or target therefore does not delete its
history. Email changes do not rewrite earlier entries. The admin exposes audit
entries read-only, including to superusers. Explicit database maintenance
remains an operator responsibility; this is not a tamper-proof external ledger.

The dashboard shows the current email's ten most recent actions and links to the
complete, paginated audit. Campaign snapshots are visible only to superusers in
both recent actions and the full audit, using `LogEntry.for_admin_user()`. This
also applies after an administrator becomes staff. Other permitted history stays
available. Entries older than that preview remain searchable by email, target
and message. An administrator who changes email can find earlier entries using
the full history. Task results expire after 30 days and export history follows
its existing separate policy; neither expires audit entries.

## Recorded actions

The action flags distinguish Addition, Change, Deletion and Action. Normal
Django add/edit/delete flows retain their object history and structured inline
change descriptions. Bulk CRUD retains a record for each affected object.

Operations use Action rather than Project Change. A single-project request
records its target; **Recompute all** records one entry for the whole request,
including an empty eligible set. Details retain operation, force option, project
count, target UUID/name snapshots, task IDs and group ID. An explicit rerun is
another administrator request. The entry says **requested**, never that the
worker completed successfully. An accepted request remains recorded when broker
delivery is uncertain.

Permission revoke/restore, email verification and schedule mutations record
their successful transitions. Manual schedule execution records the request, not
the eventual task outcome. Experiment token rotation is included in the form's
single change record without recording token values. Existing export retry,
notification retry, partial replacement and cleanup-restart actions retain their
audit coverage.

The following do not create admin audit entries:

- Worker progress, completion, failure, duplicate delivery or child tasks.
- Automatic upload generation and ordinary scheduler dispatch.
- Ordinary browsing, downloads, exports or unrelated application/API activity.
- Confirmation-page views, invalid requests and rolled-back changes.

## Integration boundaries

The custom `SpeleoDBAdminSite` applies its audit integration when registering
model admins, including third-party admins. The shared logging hooks write
application `LogEntry` records instead of Django's built-in table.
Object-history views and the dashboard use the same application model and email
snapshots. Permissions and ordinary model-admin behavior remain with their
existing owners.

`LogEntry.record()` records an explicit action with an actor email, action flag,
optional target object, message and details. Model labels use Django's
lowercase, proxy-aware label. Messages retain Django's structured change
descriptions or a readable plain string. Historical messages that do not match
Django's structured format are displayed as their original escaped text, without
rewriting stored history or preventing access to the audit. Do not attach
auditing to model-save signals, task signals or request-wide middleware: those
boundaries cannot distinguish administrator intent from its side effects.

`background_jobs.operations.schedule_operation()` records the request in the
same transaction that creates its task/group results. Publication still happens
after commit. `_create_task()` and `operation_execution()` do not write audit
entries. Technical requester IDs remain in task metadata; audit attribution uses
only the email snapshot. Deleting the requester cannot turn a successful task
into an audit foreign-key failure because workers do not write audit entries.

The application audit replaces Django's built-in admin log for all active admin
readers and writers. Django still owns its installed table; it is not a runtime
fallback and receives no dual writes from application auditing.

## Historical audit records

`users.0011_copy_admin_history` copies Django admin history into the application
log, preserving primary keys, timestamps, flags, object IDs, target descriptions
and original messages, then resets the destination primary-key sequence. Actor
emails are snapshots from the linked accounts at copy time; missing content
types remain unattributed. The migration cannot recover entries already deleted
from the source table.

The retained Django table is available for deliberate investigation, not as a
runtime fallback. Do not drop newly accumulated application audit history during
rollback or maintenance. For a database that has not yet applied the copy, back
up the database, pause administrator writes and drain old operation workers
before migration. Deploy matching web and worker code, preserving the
lightweight worker admin setup. Compare source and destination counts and
representative records, check ordinary admin edits and operation requests, and
verify that worker completion adds no audit rows before resuming activity.

## Optional historical cleanup

Run historical cleanup only after reviewing its preview. From the deployed
application's `/app` directory in the intended environment:

```sh
python manage.py cleanup_admin_task_logs --dry-run
python manage.py cleanup_admin_task_logs --apply
```

Without `--apply`, the command only previews. It reports candidate entries and
counts, then deletes transactionally only when explicitly requested. Its scope
is the application audit table, not the retained Django source table.

Candidates must match the exact historical Project Change outcome format: a
recognized project/history operation, UUID task ID, completed/failed stage and
the expected summary structure. Submission entries, genuine model changes,
malformed or uncertain messages and unrelated records remain untouched. The
command does not guess which historical per-project submissions shared a global
request. It does not change task results, projects or source history.

Preview and apply create no audit records, including no Deletion entries. A
second apply finds no previously removed rows. This optional cleanup is the
explicit exception for known historical noise, not an ongoing retention policy.

## Verification and performance

Behavioral tests exercise real admin requests, task publication and result
storage. They cover one audit entry per operation request, no worker entries,
explicit reruns, rejected/rolled-back requests, email snapshots surviving
account and target deletion, read-only administration, migration preservation,
and exact cleanup selection with no audit side effects. Existing task exception
and export-recovery regressions remain in place. Server-rendered history and
permissions belong in pytest rather than browser tests.

Run focused tests and the full backend suite in the existing application
container. Include mypy after model/caller changes, migration checks and the
template/frontend checks for the admin templates.

Operation requests add one audit insert regardless of project count; workers add
none. Target snapshots and task IDs grow only with that explicitly selected
scope. History uses indexed actor/time and target lookups with pagination. No
queue, recurring cleanup, result mirror or recovery service supports this audit.
