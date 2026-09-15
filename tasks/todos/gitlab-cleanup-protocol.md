# GitLab cleanup protocol

- [x] Trace the CI failure against the actual command, SDK, and server logs.
- [x] Select test settings in the cleanup Makefile target and report safe error
      details.
- [x] Exercise the actual management-command entrypoint against disposable
      GitLab resources.
- [x] Reproduce repeat-cleanup HTTP 400 and skip projects marked for deletion.
- [x] Run direct focused pytest, Ruff, and mypy; document the result.

## Evidence and scope

Run 35033828799 authenticated and listed 440 projects. GitLab accepted the first
DELETE with HTTP 202 at 23:03:07 UTC. `manage.py` defaults to local settings,
which force HTTP; Railway redirects HTTP to HTTPS with 301. python-gitlab
rejects redirected writes after the response. Existing cleanup tests selected
test settings directly and missed the Makefile entrypoint's local-settings
default.

Use test settings for this test-only cleanup command. Preserve local GitLab's
HTTP configuration and the remote instance's HTTPS configuration. Keep existing
confirmation and deletion scope; verification uses disposable subgroups only. Do
not run hooks or push changes.

## Review

The Makefile target now explicitly loads test settings. Cleanup skips projects
already marked for deletion and reports safe exception types/HTTP status. Actual
CLI tests use disposable subgroups, validate repeated cleanup, and assert that
an invalid token fails with HTTP 401 without printing the token.

All 10 cleanup tests passed in 29.67 seconds against local GitLab. Direct Ruff,
format, mypy (both changed Python files), and whitespace checks passed. A
credential-free DELETE to the nonexistent remote project 0 reproduced
RedirectError through HTTP and authentication rejection through HTTPS. The
shared remote CI group was not wiped during verification; the workflow needs the
published fix before its next run. No hooks were executed.
