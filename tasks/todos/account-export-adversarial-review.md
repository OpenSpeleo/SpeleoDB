# Account export adversarial review

## Scope and authorization

Review the complete export feature for actionable correctness, access, recovery,
compatibility, and regression defects. The invoked review-agent skill authorizes
the corrective work, Docker verification, and a final commit. Push and
deployment remain paused. Preserve the existing Django and webserver containers.

## Corrective plan

### Backend recovery

- [x] Review archive sources, permission selection, lifecycle transitions,
      notifications, cleanup, API/admin access, and their integration tests.
- [x] Review and narrow the corrective plan to a confirmed recovery defect.
- [x] Keep the notification retry limit when recovering an expired send lease.
- [x] Add a database regression covering a process lost during its final send,
      rejected automatic redelivery, and an explicit operator retry.
- [x] Run the focused lifecycle tests inside the existing Docker container.

**P2 — Exhausted notification leases receive unlimited automatic retries.**
`speleodb/background_jobs/tasks.py`, `maintain_background_jobs`: a process that
dies after claiming its fifth notification leaves an expired `sending` lease.
Maintenance currently resets that lease to `pending` regardless of its recorded
attempt count, allowing a sixth send and repeated subsequent sends. Recover
leases below the existing five-attempt limit; mark exhausted leases failed and
clear their claim token and due time. Keep manual notification retry available.

Plan review: keep the existing notification lifecycle and retry budget. No new
fields, infrastructure, settings, or delivery guarantees are needed. A database
test should model the lost lease directly and verify that manual retry remains
independent of archive generation.

### Root-owned corrections

- [x] Remove the unrequested export encryption settings and upload requirement;
      preserve ordinary ZIP files and the bucket's existing configuration.
- [x] Route existing unqualified Celery tasks to `background_control`, which the
      single worker consumes, and verify actual routing.

**P2 — Existing Celery tasks are routed to an unconsumed queue.**
`config/settings/base.py`: the worker consumes `exports,background_control`, but
Celery's implicit default is still `celery`. Existing survey refresh and user
count tasks without explicit routes would remain queued indefinitely. Set the
default queue to `background_control` and test a real unqualified task delivery.

### Final verification and delivery

- [x] Run the complete Python and JavaScript test suites inside Docker.
- [x] Run the relevant live worker and storage integration checks inside Docker.
- [x] Run `prek run -a` inside Docker and review the final staged diff.
- [x] Commit the reviewed changes; do not push or deploy.

## Review results

The notification regression failed before the fix: maintenance returned the
exhausted lease to `pending`. After the fix, all 16 lifecycle tests passed in
Docker, including lease recovery below the limit and manual retry after the
limit. Ruff checking and formatting passed for the changed backend files.

Actual Celery router checks passed for all six covered task routes. All five
isolated live-worker tests passed, including an existing task without a queue
override, export download and notification, expiration, duplicate delivery,
broker refusal, and process-death recovery. The temporary test broker was
removed afterward.

The real ZIP64/S3 check passed after removal of the encryption override:
4,294,967,313-byte archive member, verified uploaded/downloaded checksums, and
bounded memory. The complete JavaScript suite passed all 1,003 tests.

Final Docker verification passed 4,269 Python tests and 108 subtests, with 163
skips, plus every applicable `prek run -a` hook. Django system checks passed and
the migration dry run found no changes. An authenticated request to the running
export page returned HTTP 200, one export list, and the exact built assets from
the production manifest. Push and deployment remain paused.

After the checks, the idle Celery worker was restarted once and verified to
consume both queues. Django and the webserver were not manually restarted or
recreated. The feature and these corrections are committed together with this
review record.
