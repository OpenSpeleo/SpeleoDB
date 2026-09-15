# Git explorer error capture

## Plan

- [x] Read repository guidance and trace the reported pull failure through the
      Git retry wrapper and explorer exception handler.
- [x] Verify the existing API, logging, Sentry, and frontend contracts;
      establish whether the report concerns capture, response clarity, or the
      remote failure.
- [x] Make the smallest evidence-backed correction, if needed, and add focused
      regression coverage for any changed behavior.
- [x] Run relevant verification and document the result and operational limits.

## Initial findings

The reported `GitBaseError` already matches the explorer handler. That handler
logs a traceback, explicitly calls `sentry_sdk.capture_exception`, and returns a
JSON `ErrorResponse` with HTTP 500. The second Django log line is consistent
with that intentional response. The original failure is a Git pull reporting
that the configured remote repository could not be found. These logs alone
cannot establish whether the repository is absent, inaccessible, or
misconfigured, or whether Sentry actually received the event.

## Review

Source inspection and an independent read-only audit confirm that this exact
exception is caught. Existing `ProjectExplorerSentryTests` cover HTTP 500 and an
explicit capture call for the same checkout failure. Django's installed request
handler logs returned 5xx responses as errors, explaining the second log line.
No missing exception handler is demonstrated, so application code and tests were
left unchanged. No runtime tests were run for this investigation.

The failure message attributes the problem to checkout even though the pull
fails first. The frontend `git-view` controller logs failed requests only to the
console, and renders no error notice. These are separate response-clarity
issues; they do not indicate that the backend exception escaped capture.

Production Sentry initialization is conditional on `SENTRY_DSN`. Code inspection
cannot prove delivery to Sentry or distinguish a missing repository from GitLab
access/configuration problems. The user was asked which symptom prompted the
report; no response was available during this investigation. Existing unrelated
workspace edits are outside this task.
