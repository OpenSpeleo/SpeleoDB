# Export source availability and one presentation per request

A successful Git clone does not prove the remote still contains the expected
history. If a project has recorded commits but its cloned remote is empty,
report an omission instead of substituting an empty-project marker.

When polling replaces history cards, restore keyboard focus to the same
surviving card or action. Keep explicit deep-link focus separate, and do not
steal focus from controls outside the history.

Do not bulk-delete retryable job history from a state-filtered queryset. Django
collects related rows before deleting the parent; a concurrent accepted retry
can be collected in between. Lock and recheck each job before cascading, and
return a controlled unavailable response when deletion wins the race.

Keep backup scope to the requested product. Do not introduce export encryption
requirements, encryption settings, or backend-specific overrides without a user
requirement. Use ordinary ZIP files and the bucket's existing storage policy.
Distinguish storage encryption from ZIP passwords when explaining behavior.

Exports must clone every eligible GitLab repository into isolated temporary
storage, including projects with no local checkout. Test this explicitly with a
real remote and multiple historical revisions. Never call create-or-clone from a
backup: it can replace a missing remote with an empty new repository.

Distinguish missing local checkouts from repositories unavailable on GitLab.
GitLab 404 responses can indicate absence or inaccessible repositories; report
that source ambiguity accurately and verify configuration before claiming a disk
dependency.

Local namespace drift can make existing repositories appear missing. The
reported projects were under `speleodb_surveys_dev`, while `.envs/.django`
forced `speleodb` and bootstrap rewrote the private environment accordingly.
Compose must interpolate the chosen namespace from the private root `.env` for
both bootstrap and application services; tracked defaults must not shadow it.
Check the existing GitLab namespaces before declaring repositories absent.

Project creation does not imply remote repository creation: SpeleoDB initializes
GitLab lazily on first upload. A zero-commit project can therefore legitimately
have no remote. Try cloning first to preserve any unindexed remote history, then
verify namespace access and remote metadata before representing that state with
the zero-byte `PROJECT IS EMPTY` marker. Mark it informational, not omitted.
Never invent a commit or create a remote during backup; known recorded history
must still make a missing remote an omission. Cover both DB-only and remotely
empty projects with real GitLab tests.

Celery does not reload bind-mounted Python code automatically. Distinguish a
source fix from a fix running in the local worker: restart the worker after the
focused checks, generate a fresh affected-user export, and inspect its actual
ZIP before reporting the behavior fixed. Existing archives remain unchanged.

Backups must be immediately usable after extraction. Populated project folders
contain their checked-out files alongside `.git/`, preserving complete reachable
history. Do not make users clone a `repository.git` directory to access their
files. Zero-commit projects contain only `PROJECT IS EMPTY`, with no extension
and no Git directory. Downloads use `speleodb-export-{datetime}-{uuid}.zip` with
a filesystem-safe UTC timestamp including time through seconds.

Do not restart or recreate Django or the webserver while iterating on exports.
Run checks in existing containers or isolated one-off test containers without
bringing up the full Compose graph. Apply completed worker changes with one
worker-only restart after verification; preserve the user's running web session.
Container uptime alone does not prove Django stayed up: its automatic reloader
also watches generated files unless configured otherwise. Local development uses
the stat reloader and excludes `.workdir` to avoid test Git churn and Docker
watchdog/inotify races. Verify that real application changes still reload.

Show simple active-job copy: `An email will be sent when ready to download.`
Keep technical stage/item counts in operations tools. Filter expired archives
before API pagination and when merging/rendering the page, so deep links and
open tabs cannot bring expired cards back. Keep pending jobs and failed retries
visible.

Show each export request once. A selected/deep-linked export and the recent
history must not become duplicate cards or competing sections. Merge the
selected request into one list while preserving direct links and polling.
