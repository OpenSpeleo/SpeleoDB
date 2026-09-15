# Bounded operational retries

## Intent and confirmed failure

A finite attempt count is insufficient when an individual call or retry sleep
can wait indefinitely. CI run `34997387739` exposed that distinction: its stack
dump stopped in python-gitlab's server-directed retry sleep during the first
Compass upload test's project creation. The preceding exploration-lead tests
had completed. The exact server status/header was not captured.

Operational failure recovery must have a finite budget, capped exponential
delays, and bounded blocking calls where the application controls them. A
successful periodic status check, scheduler tick, or WebSocket receive loop is
a service lifecycle, not an automatic retry of a failed operation.

## Policies and ownership

| Operation | Budget and delay | Exhaustion behavior |
| --- | --- | --- |
| GitLab REST | Five total attempts; 1/2/4/8-second backoff, capped at 30 seconds; 30-second request timeout (15 in bootstrap) | Original SDK error propagates; server delay headers cannot extend sleep |
| Git remote operations | Five attempts; 1/2/4/8-second backoff; 60-second command deadline and five-second cleanup | Sanitized Git error; no automatic deletion of the working copy |
| Git proxy discovery GET | Five attempts; exponential delay capped at 30 seconds | Final response/error; a longer server delay returns immediately |
| PostgreSQL container readiness | Six attempts; 1/2/4/8/16-second backoff; five-second connect timeout | Entrypoint exits with failure |
| Celery broker connection | Five retries after the initial attempt; 1/2/4/8/16-second backoff | Connection error leaves worker startup/reconnection |
| Beat ownership lock | Six attempts; 5/10/20/40/80-second waits | Command error; shutdown also bounds child termination |
| Export generation/publication | Three attempts per cycle; 60/120-second delays | Durable failed job; explicit retry creates a fresh cycle |
| Export notification publication/delivery | Five combined attempts; 60/120/240/480-second delays | Durable failed notification; explicit staff retry |
| Artifact and orphan cleanup | Five persisted attempts; 60/120/240/480-second delays | Error/counters retained; audited staff action resets budget |
| Export browser refresh | Five failed refreshes; 5/10/20/30-second delays; 30-second request/JSON deadline | Error message and no automatic network retry until explicit action/reload |
| GeoJSON cache contention | Seven cache rechecks; 0.1/0.2/0.4/0.8/1/1/1-second waits | Direct storage fallback; fewer cache operations than the previous 50 checks |
| FFmpeg thumbnail | One execution; 60-second process deadline, five-second cleanup | Existing thumbnail error path |

The shared retry helper validates finite delay parameters and positive attempt
counts, doubles delays iteratively up to a cap, and never sleeps after the final
failure. GitLab uses a pure-Python transport shared with Compose provisioning.
The Git proxy only retries discovery reads before consuming the response; Git
protocol POSTs are not replayed. GitLab transient writes still require explicit
opt-in, preserving the existing project-create conflict confirmation contract.

Git commands run in isolated POSIX process groups so terminating a command also
terminates its ordinary helpers/hooks. Streamed GitPython operations and
synchronous operations use the same deadline owner. Export Git supervision also
retains its liveness pipe for cleanup after a killed Celery process. Post-kill
waits are bounded; `Popen` context-manager exit cannot add an unbounded wait.

Celery's consumer and database-scheduler extensions share a broker retry helper,
because Kombu's standard connection retry delay is linear. Worker startup/runtime
retry flags, failover, and shutdown checks remain supported. Beat's launcher
reads the scheduler class from settings so its CLI cannot bypass this policy.
Redis cache connections now explicitly bound connection/read socket waits.
Existing storage SDK retry budgets and Celery result-backend retry limits remain
finite and unchanged.

## Durable export recovery

Retry counts belong to the database, not a scheduler invocation or worker
process. Broker publication failures and expired publication leases consume a
generation attempt; notification publication and delivery share one counter.
Ownership tokens reject late notification and cleanup completions. Unknown
cleanup outcomes wait for the fixed owner lease plus exponential cooldown;
reported failures can schedule their cooldown immediately. All durable export
delays cap at one hour.

Job and attempt creation explicitly read Django's `timezone.now()`. The shared
attempt-creation service assigns one instant to both `created_at` and
`dispatch_after`, so new requests and automatic/manual retries are immediately
eligible under that same clock. This avoids model default callbacks retaining a
different clock during controlled-time tests. Lease boundaries and retry budgets
remain unchanged, with no additional queries or schema migration. Regression
tests check failed publications across a whole retry cycle and confirm stale
publications remain queued just before their lease, then fail at the deadline
without republishing.

Migration `0002_attempt_cleanup_budget` adds the publication marker and per-object
cleanup fields. Apply it before updated application/worker code. Exhausted
cleanup retains tracking rows instead of discarding evidence that objects still
exist. Expired downloads remain unavailable even when deletion is failing. Staff
can use **Retry exhausted artifact cleanup** in job administration; resets are
recorded in Django's admin log.

Healthy browser polling continues while an export is active. Only consecutive
failures exhaust its budget. Successful refreshes, explicit submissions, and
pagination reset that budget; a visibility change does not bypass backoff.
Automatic POST retries are prohibited. Local expiry rendering can continue even
after network retries stop.

## Verification and limits

Regression cases cover SDK exhaustion and hostile delay headers, Git process
and hook hangs, descendant-held pipes, cleanup timeouts, broker and lock retry
budgets, durable publication failures, lost workers, stale completion tokens,
cleanup retention/admin recovery, and browser cancellation/body timeouts.
Existing lifecycle/live-worker expectations were updated to the new contracts.

**Python and JavaScript tests have not been rerun**, following the user's
instruction. Earlier successful test runs in other documents predate this change
and do not validate it. When test execution is authorized, run them inside
Docker, including real PostgreSQL/worker/process-containment cases and the
migration path.

After correcting the user's reported typing/lint failures, direct Docker checks
passed: mypy checked all 705 source files, and Ruff checked `speleodb`, `config`,
and `compose`. This included new unstaged files omitted by the hook's tracked
file inventory. No full pre-commit hook run was performed by the assistant.

These limits do not impose one wall clock over every repository/database/filesystem
operation. HTTP read timeouts bound inactivity, not an entire continuously
streaming transfer. GitPython's cached `cat-file` readers are long-lived and
retain their normal lifetime. Operating-system I/O and processes deliberately
escaping an owned process group require external containment. A finite retry
budget exposes a persistent remote outage; it does not repair GitLab itself.
