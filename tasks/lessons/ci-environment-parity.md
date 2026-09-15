# Verify subprocess and integration tests against the CI environment

When the user explicitly asks to push a CI diagnostic change without testing,
make the requested change and push it. Do not add tests or pre-commit checks
after that instruction.

Local Compose credentials and private dotenv files can hide missing CI inputs.
GitHub Actions service environment variables configure the service container;
runner-side integration tests need their own explicit connection variables.

A default in Django test settings does not populate `os.environ`. Tests that
launch a subprocess with another settings module must supply that module's
required inputs, disable private dotenv loading, and include captured stderr in
failure assertions.

Reproduce CI failures from a disposable tracked checkout with the workflow's
environment before fixing them. Re-run the same behavioral tests afterward,
including real database provisioning when that is the contract under test.

When diagnosing a reported CI failure, inspect that run's evidence before
proposing unrelated infrastructure causes. If the user rules out overlapping
jobs or cleanup, accept that constraint and focus on the failing request and
fixture. Keep hypotheses distinct from confirmed causes.

For a stall at a test-module boundary, get the actual next node from full pytest
collection. A truncated file listing or guessed lexical order can select the
wrong reproduction. Print the effective Django database engine inside the test
environment; a running PostgreSQL container does not mean pytest uses it, and
private test dotenv files may select SQLite. Record these limits before using
local timings to assess CI behavior. Add a faulthandler stack dump when
finalized logs contain no blocked-call evidence.

The September 2026 stack confirmed python-gitlab sleeping on a server-directed
retry delay. Always inspect SDK sleep behavior as well as request timeouts and
retry counts: a finite count can still mean a multi-hour wait. Reject infinite
retry sentinels, cap exponential backoff, and bound individual operations and
post-kill cleanup. Check scheduler-level requeue paths too; resetting counters
on each sweep recreates an infinite retry loop across otherwise finite tasks.

When extending GitPython process ownership, narrow optional `AutoInterrupt.proc`
before using/transferring it, and normalize command sequences to the exception
constructor's declared type. Assert nullable current-attempt IDs before ORM
lookups in regressions. Any untyped third-party constructor needs a narrowly
scoped annotation; source review cannot establish that mypy passes when checks
have not been run.

Include new, unstaged files in direct lint/typecheck coverage: the hook's Git
file inventory can omit them. For upstream runtime methods missing from stubs,
document the stub gap instead of claiming a typed override. Mock read-only
properties with `PropertyMock`, and keep setup outside `pytest.raises` blocks.
