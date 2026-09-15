# CI progress masking and Git checkout diagnostics

- [x] Identify the group ID secret as the masking candidate and audit consumers.
- [x] Update CI and cleanup workflows to read the non-secret Actions variable.
- [x] Create and verify repository variable GITLAB_GROUP_ID=3.
- [x] Delete the obsolete group-ID secret and verify its removal, as explicitly
      requested by the user before committing.
- [ ] Push the commit before the next CI or scheduled cleanup run.
- [x] Accept both observed missing-tree diagnostics while requiring a failed
      checkout of the exact requested SHA and unchanged repository/database
      state.
- [x] Verify the real checkout regression, lint, types, and workflow
      configuration.
- [x] Document migration ordering, verification, and lessons.

The user explicitly requested secret deletion and a local commit, with no push.
The published workflows still reference the removed secret, so the commit must
be pushed before the next CI or scheduled cleanup run. No prek or pre-commit
hooks are executed.

## Review

All five real checkout/history tests passed. The missing-commit case accepts
both observed Git messages while checking status 128, the exact checkout SHA,
unchanged HEAD, and no reconstructed database history. Ruff, formatting, mypy,
and diff checks passed. Both edited workflow files parse as YAML and use the
Actions variable while retaining the token secret.

GitHub readback confirms the repository variable is `3` and the group-ID secret
is absent. The GitLab access-token secret remains configured. Workflow
publication remains outstanding; no new CI run is claimed.
