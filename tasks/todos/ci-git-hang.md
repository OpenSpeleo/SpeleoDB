# Diagnose CI pause after exploration-lead tests

## Plan

- [x] Inspect the last reported test module, upload tests, fixtures, teardown,
      and Git/network call boundaries without assuming the printed module caused
      the pause.
- [x] Verify the Docker test configuration targets the local GitLab service.
- [x] Run the exploration-lead module and a GeoJSON upload test inside the
      existing Django container with verbose output, durations, and a 30-second
      faulthandler stack dump.
- [x] Compare local evidence with the affected CI run before identifying a root
      cause.
- [x] Print individual test names and dump the Python stack after 60 seconds in
      a test, then verify the CI pytest options inside Docker.
- [x] Verify full-suite collection order and the effective local database
      engine.
- [x] Identify the exact blocked call from the CI stack (supersedes the pending
      local PostgreSQL reproduction, which the user instructed us not to run).
- [x] Record findings and the bounded-retry correction; execution remains
      paused.

## Evidence and scope

Upload tests provision GitLab projects and push initial commits. Git
subprocesses currently have no command deadline. GitLab API requests have
bounded attempts and request timeouts, but the client permits server-directed
rate-limit sleeps without a wall-clock cap. PostgreSQL waits also require
consideration because the initial local reproduction used SQLite. Runtime
evidence is required before attributing the reported CI pause to any of these
paths.

Tests use the existing local Docker services, with no container restarts or
pre-commit checks. The user canceled both affected CI runs to finalize logs.

## Review

The focused Docker run passed: **153 passed, 21 skipped in 15.21 seconds**. The
real local GitLab upload test took **3.48 seconds**. Initial database setup took
7.89 seconds; the slowest exploration-lead test call took 0.43 seconds, and the
slowest teardown took 0.16 seconds. No 30-second faulthandler dump occurred.
This run does not reproduce the CI stall and does not establish its cause.

Command:

```sh
docker compose -f local.yml exec -T django pytest -vv \
  -o faulthandler_timeout=30 --durations=15 \
  speleodb/api/v2/tests/test_exploration_lead_api.py \
  speleodb/api/v2/tests/test_file_upload_geojson.py::TestFileUploadGeoJSON::test_upload_ariane_generates_geojson
```

## Affected CI runs

- Run `34985852182`, pytest job `104452357610`.
- Run `34985861022`, pytest job `104452374803`.

Both runs' linter and JavaScript jobs passed. While pytest was running, GitHub's
job-log download endpoints returned missing blobs (`BlobNotFound`, HTTP 404).
After the user canceled both runs, finalized logs became available.

The first run's last progress line is at 15:43:43 UTC, with cancellation at
16:06:51 UTC. The second has the same progress at 15:43:46 UTC, with
cancellation at 16:06:53 UTC. Each has about 23 minutes of silence. Neither
contains a Python traceback, GitLab error, or HTTP retry diagnostic. Cleanup
terminates the orphan pytest process. Cancellation did not recover the blocked
Python stack.

These logs do not identify the blocked call. CI needs stack diagnostics before
changing application behavior based on a suspected Git, REST, or database wait.

## Corrected collection and environment evidence

Full Docker collection produced 4,453 tests. The actual immediate successor is
`speleodb/api/v2/tests/test_file_upload.py::FileViewTests::test_upload_auto_compass_bundle_does_not_validate_mak_dat_references`.
The initial GeoJSON test selection came from an incomplete file inventory and
does not establish the behavior of this immediate successor. Runtime inspection
also confirmed the local test database was SQLite, while CI uses PostgreSQL.

The actual next test uploads an incomplete Compass bundle and downloads a ZIP.
It uses the same GitLab provisioning, initial push, and upload path as the
GeoJSON test, then performs an additional pull for the download. Shared setup
creates database rows; no additional remote initialization fixture was found.

With the proposed CI options, the full exploration and GeoJSON-upload files
passed locally: **157 passed, 21 skipped in 19.89 seconds**. The first GeoJSON
upload took 3.03 seconds. This still used SQLite and local GitLab.

The exact-successor PostgreSQL run was blocked by Docker socket permissions. Its
pending retry was stopped. No PostgreSQL test result is available yet.

The user requested `-vvv -s` and explicitly instructed us to push without
further tests. The workflow retains the 60-second stack dump and duration
summary. No application retry behavior changed. Diagnosis continues from the
next CI run's uncaptured output and stack evidence.

## Confirmed diagnostic run

Run `34997387739`, job `104476947867`, emitted a 60-second faulthandler dump at
2026-09-15 16:52:14 UTC. The stack is in `gitlab/utils.py:138`,
`handle_retry_on_status`, called by project creation in
`test_upload_auto_compass_bundle_does_not_validate_mak_dat_references`.
Exploration-lead execution and teardown had completed. The HTTP timeout and
retry count did not bound the SDK's server-directed sleep. The exact response
status and header value are not present in that dump.

Implementation and source-review status are tracked in
[bounded-retries.md](bounded-retries.md). No additional tests or hooks were run
after the user's no-testing instruction. The earlier local results above do not
validate the new retry changes.
