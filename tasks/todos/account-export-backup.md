# Account export and background jobs

Approved design: PostgreSQL-backed Celery results and application job/attempt/
artifact records, the existing Redis shared by cache and Celery, one worker
consuming both queues, Celery Beat, and independently authenticated Kanchi with
its own database/user on the existing PostgreSQL server. **No Railway cron
services or Railway cron schedules.**

## Review correction: consolidate infrastructure

The user authorized these corrections during review. The later `review-agent`
invocation authorizes a commit after corrective work and full container checks.
Pushes and deployment remain paused; the deployment configuration is prepared
for a later rollout.

- [x] Replace export/maintenance services with one `celery-worker` consuming
      `exports,background_control`; scale by adding replicas of that service.
- [x] Reuse Redis on port 6379: cache database 0, Celery database 1, durable AOF
      storage and no eviction. Keep the isolated integration-test broker opt-in.
- [x] Provision a separate Kanchi database/user on the existing PostgreSQL
      server, including when the existing data volume is already populated.
- [x] Preserve existing local cache/broker data and Kanchi history during the
      switch, then remove only the obsolete containers, retaining old volumes.
- [x] Update Railway IaC to reuse the existing databases and deploy only one
      worker service, Beat, and Kanchi.
- [x] Update tests, operations docs, and lessons; run all tests and required
      checks inside Docker, then verify both queues and Kanchi in the live
      stack.

## Product contract

### Additional review corrections

- [x] Replace selected/recent export sections with one deduplicated list while
      preserving direct links, polling, download, and retry actions.
- [x] Explicitly test full remote cloning without a local checkout and clarify
      remote missing/access errors. Correct the local namespace drift: all seven
      reported repositories exist under `speleodb_surveys_dev` and now return
      authenticated GitLab 200. Compose preserves that private configuration; 17
      namespace/bootstrap regression tests passed. Repositories were not moved
      or recreated.
- [x] Include valid zero-commit projects whose GitLab repository has not been
      initialized, without fabricating commits or hiding missing recorded
      history.
- [x] Export populated projects as directly readable working files alongside
      `.git/`, preserving all advertised refs and reachable history.
- [x] Export zero-commit projects with only a zero-byte `PROJECT IS EMPTY`
      marker, without any Git directory.
- [x] Name downloads `speleodb-export-{datetime}-{uuid}.zip`, using UTC date and
      time through seconds and the export job UUID; verify the actual download
      response's filename.
- [x] Verify the corrected ZIP layout and naming inside Docker, reload only the
      Celery worker once the checks pass, and inspect a fresh affected-user ZIP.
      Do not restart or recreate Django, the webserver, or the Compose stack.
- [x] Stop generated Git/test files from triggering Django's automatic reloader:
      use the stat reloader locally and exclude `.workdir` data. Verify scratch
      changes/deletions are ignored while application code still triggers
      reload.
- [x] Replace active export stage/counts with the requested email message and
      hide expired exports in API pagination and the UI, including linked cards
      and cards expiring while the page remains open.

- Five archive categories: project files and full Git history, latest project
  GeoJSON, GIS uploads plus distinct processed data, GPS GeoJSON plus bounded
  GPX, landmark collections.
- Minimum READ_ONLY; permission snapshot at generation start, fresh on retry.
- Partial results report omissions; one active export per user, no daily quota.
- Login-required email link; private S3 exports prefix; 24-hour availability
  from readiness, five-minute signed links, recurring deletion and lifecycle
  fallback.
- Staff inspect/retry; owner and superusers download; staff production pilot.

## Implementation

Implementation and container verification are tracked separately below.
Production acceptance remains pending while deployment is paused for review.

- [x] Add `django-celery-results==2.6.0`, remove Flower, update `uv.lock`.
- [x] Write durable job/attempt/artifact models and the explicit initial
      migration, with guarded dispatch, recovery, and terminal task-result
      preservation.
- [x] Write permission snapshots, bounded archive generation, manifests, full
      Git mirrors, and shared landmark collection GeoJSON serialization.
- [x] Write private object storage, expiry/deletion, tracked notifications,
      exact key multipart cleanup, and storage-policy preview/apply commands.
- [x] Write APIs, account export UI with direct-link retrieval independent of
      pagination, controlled Django admin actions, and read-only technical
      results.
- [x] Write escaped HTML/plain notification emails with archive size and expiry.
- [x] Update Compose: shared durable Redis, one worker for both queues,
      singleton Beat, Kanchi on a separate database/user in the existing
      PostgreSQL server, and an opt-in isolated integration-test broker.
- [x] Update startup scripts, migration fail-fast behavior, environment
      precedence, devcontainer forwarding, and remove Flower
      startup/configuration.
- [x] Write database schedules, Beat standby/advisory-lock shutdown handling,
      and tagged Kanchi progress events including completed publication
      progress.
- [x] Write focused backend/API/admin/frontend tests, real source/storage tests,
      and opt-in PostgreSQL/Redis/RustFS worker tests plus a container-only
      runner.
- [x] Write feature, API/UI, storage-policy, and operations documentation.
- [x] Prepare additive Railway IaC while preserving the existing named partial
      and web configuration; no external resources have been changed.

## Completed local verification

- [x] Docker Desktop available; full Compose graph built and started
      successfully, preserving existing named volumes. Django runs Python
      3.14.7/Django 6.0.8.
- [x] Additive migrations and installed schedules checked inside Docker;
      `makemigrations --check --dry-run` reports no missing model changes.
- [x] Install `railway@3.11.0` and minimal pinned TypeScript tooling inside
      Docker, updating the root manifest and lock together.
      `npm run typecheck:railway` passes. The consolidated read-only live
      Railway plan reports seven safe changes, zero removals, and zero
      diagnostics: three new services (worker, Beat, Kanchi) plus existing web
      configuration.
- [x] Verify the new image manifests through Docker Registry API inside Docker:
      response digests match actual manifest bytes and include amd64/arm64.
      Redis and Kanchi are pinned; the existing PostgreSQL server is reused.
- [x] Kanchi startup/own database healthy; anonymous task history denied, login
      verified, one worker observed, actual maintenance/cleanup events ingested.
      All history retention is 30 days, daily cleanup is enabled at 03:00 UTC,
      and configuration/history survive a Kanchi restart.
- [x] Focused lifecycle tests: 11 passed. API/admin/frontend URL tests: 51
      passed.
- [x] Full JavaScript suite after the single-list correction: 989 passed.
      JavaScript lint and clean production build passed. Authenticated live
      page/history requests return HTTP 200; served controller/app/CSS bytes
      match production manifest
      `9bab2f6469cb51c19bc5a5ebc204fb59037620bd7ffa43cbca3d07fc4fa64fa7`. The
      rendered page contains exactly one export list and no selected/recent
      sections.
- [x] Before consolidation: full Python suite passed 4,230 tests and 108
      subtests; all pre-commit checks and mypy (687 files) passed. Live worker
      and PostgreSQL/Compose checks passed 16 tests, including actual SIGKILL
      and recovery. The archive larger than 4 GiB passed real upload/download
      checksum verification at approximately 405 MiB peak RSS.
- [x] Consolidation: 11 real PostgreSQL bootstrap tests and eight Compose/worker
      startup tests passed. Kanchi migration preserved all 21 tables and 321
      rows; cache/broker data was transferred and survived a Redis restart. Old
      containers were removed with volumes and the database dump retained.
- [x] The consolidated runtime generated and notified a synthetic empty export
      in 0.80 seconds. Generation and maintenance recorded the same worker
      identity; the signed 1,791-byte ZIP checksum and all five directories
      matched. Synthetic records, object, and local mail were removed.
- [x] Full Python suite after consolidation: 4,240 passed, 162 skipped, and 108
      subtests passed. Four isolated real-worker tests passed again, including
      actual worker death and recovery. Scaling to two worker replicas produced
      distinct node names consuming both queues; scaling back left one worker
      consuming both queues. Kanchi remains healthy and authenticated.
- [x] Before the working-files/marker correction, the full Python suite passed
      4,255 tests and 108 subtests (162 skipped), and all pre-commit hooks
      passed. A fresh three-project archive had no omissions and passed actual
      download checksum and Git restoration checks. Its bare-repository layout
      was then replaced by the working-files/marker layout specified above.
- [x] Final archive layout: 36 archive/supervisor cases and four live-worker
      cases passed. Full Python suite: 4,259 passed, 162 skipped, 108 subtests
      passed. After the final list/reloader changes, 54 API/admin/private URL
      and reloader checks passed. Full JavaScript suite: 1,003 passed. All
      pre-commit hooks, mypy, JavaScript lint, and clean production build
      passed.
- [x] Fresh local job `5b6bb4b1-cae6-463a-8102-2fcd5442ded7` is READY with no
      omissions. Its 305,002-byte ZIP contains `PROJECT IS EMPTY` alone for READ
      AND WRITE, and readable `ariane.tml` plus `.git/` and two commits each for
      READ ONLY and WEBVIEWER. ZIP/per-entry checksums, Git integrity, clean
      working trees, real HTTP download filename, and cache headers passed. The
      artifact is retained for review; only the worker was manually restarted.
- [x] Latest authenticated HTTP page check returned 200 and verified one list.
      Served controller/app/CSS bytes match manifest
      `e5e95988de65790f32684f0d4a1878b90bd390f37dcff607e20312f1c21cfd0a`. Expiry
      filtering, timers, deep links, and recovery when expiry invalidates a
      later page are covered by the JavaScript/API tests.

## Remaining verification and rollout

- [x] Complete the full pytest/pre-commit runs and resolve any failures.
- [x] Run isolated real-worker tests, including actual process death/recovery,
      before and after consolidation. Verify the representative large archive.
- [x] Recheck the final source state after remaining test-driven fixes.
- [ ] Finish review, resolve all failures, commit, and verify CI.
- [ ] Inventory live Railway configuration, reconcile references/ownership,
      preview the IaC plan, deploy the reviewed commit, and record deployment
      IDs.
- [ ] Complete staff pilot and production acceptance before enabling all users.

## Verification and rollout

All tests, builds, lint, and type checks must execute inside the Docker
container, as explicitly required by the user. Do not substitute host-based
verification.

Use real isolated PostgreSQL/Redis/storage/Git repositories for integration.
Verify duplicate dispatch, worker loss, stale publication, notification failure,
24-hour access enforcement, version-aware deletion, unauthorized access, and
Kanchi outage isolation. Deployment is additive, uses one application commit,
starts with creation disabled, then staff-only. Record exact deployment IDs and
results; keep cleanup and existing downloads available if creation is disabled.

### Next container commands

Use the existing containers for further verification. Do not rebuild or restart
the Django/webserver services or bring up the full Compose graph while reviewing
this feature. The completed checks above record what has already run.

```bash
docker compose -f local.yml ps
docker compose -f local.yml exec -T django uv sync --frozen --extra local
docker compose -f local.yml exec -T django npm ci
docker compose -f local.yml exec -T django npm run typecheck:railway
docker compose -f local.yml exec -T django python manage.py makemigrations --check --dry-run
docker compose -f local.yml exec -T django python manage.py migrate --noinput
docker compose -f local.yml exec -T django python manage.py install_background_schedules
docker compose -f local.yml exec -T django pytest compose/tests/ speleodb/background_jobs/tests/ speleodb/api/v2/tests/test_user_exports.py
docker compose -f local.yml --profile integration-test up -d celery-test-redis
docker compose -f local.yml exec -T django python compose/run_live_worker_tests.py -q
docker compose -f local.yml exec -T django npm run test:js
docker compose -f local.yml exec -T django npm run lint:js
docker compose -f local.yml exec -T django npm run build
docker compose -f local.yml exec -T django ruff check compose/ config/ speleodb/background_jobs/ speleodb/api/v2/serializers/user_export.py speleodb/api/v2/views/user_export.py speleodb/api/v2/tests/test_user_exports.py speleodb/gis/landmark_geojson.py frontend_private/
docker compose -f local.yml exec -T django mypy speleodb/background_jobs/ speleodb/api/v2/serializers/user_export.py speleodb/api/v2/views/user_export.py speleodb/gis/landmark_geojson.py
```

Run additional existing suites/required pre-commit checks inside Docker as the
review and CI require. Avoid parallel invocations of the live-worker tests: they
share the isolated test broker and pytest's PostgreSQL test database.

## Review

The consolidated local stack, full Python/JavaScript suites, real worker
failure/recovery, multiple replicas, and large-archive checks passed as recorded
above. The final working-files/empty-marker layout, named downloads, simplified
active-job copy, and expiry-filtered list are verified locally. The automatic
development reloader now excludes scratch data; its code-reload behavior has a
regression test. No commit, deployment, or external bucket mutation has been
performed. Live Railway inventory is read-only; the existing named IaC partial
is preserved and must be reconciled against production before applying a
reviewed plan. Browser tooling was unavailable, so visual browser inspection is
unverified; authenticated HTTP rendering and the exact served asset bytes were
checked.
