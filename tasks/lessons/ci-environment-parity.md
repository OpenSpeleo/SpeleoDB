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
