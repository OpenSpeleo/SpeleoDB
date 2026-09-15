# Connect Railway GitLab to its official image

- [x] Inspect the live source, deployment, volume, and startup configuration.
- [x] Preserve startup/configuration files on the existing volume and take a
      backup.
- [x] Attach the official GitLab CE image with an explicit persistent start
      command.
- [x] Enable patch updates with a maintenance window and verify saved settings.
- [x] Redeploy the test GitLab service and verify health, data, and credentials.
- [x] Update operational documentation, lessons, and the review.

## Scope and deployment plan

The user authorizes reconnecting and restarting the GitLab service in Railway's
test environment. The service originally ran uploaded Dockerfile deployment
3debd5be without a connected source. Keep the same service, domain, volume, and
GitLab version for the source migration; only later patch updates advance it.

Official source: `gitlab/gitlab-ce:19.3.2-ce.0`. Persist the existing `start`,
`gitlab.rb`, and `bootstrap.rb` under `/data/speleodb`, configure the
environment variables formerly supplied by the Dockerfile, and use
`/bin/bash /data/speleodb/start`. The wrapper restores the existing persistent
paths and then executes GitLab's official `/assets/init-container` entrypoint.

Enable patch-only updates rather than skipping GitLab's required minor-version
upgrade stops. Snapshot the volume before the source change. Verify the exact
new deployment reaches SUCCESS and check identity/repository persistence. The
existing application cleanup fixes are separate local changes.

## Review

- Snapshot `2804168c-5d0e-4157-8e3c-7b3eaf971315` was created before deployment;
  the backup listing reports 1,044 MB referenced.
- All three startup files on `/data/speleodb` matched repository SHA-256 hashes.
- Official-image deployment `8fd607fd-bfd5-43f7-b9f3-9bb2c0ac18e8` reached
  SUCCESS at 23:24:05 UTC. The source and explicit start command are visible in
  Railway; saved updates are patch-only, every day 09:00–10:00 UTC.
- HTTPS sign-in returned 200. All eight bundled services were running. Group
  `github-ci` remains ID 3, the configured root password validates, and original
  CI token ID 4 remains active.
- Existing project 5 retained commit `4a0f96cb7b7d1b95c43028942c6da0ba131ba6aa`.
  A temporary token for the same CI bot authenticated over HTTPS, read that
  commit, created project 664 with a README, read its contents, and scheduled
  its deletion with HTTP 202. The temporary token was revoked afterward; the
  original CI token was preserved.
- Both filesystem/startup tests passed in Docker. An initial host test attempt
  hit macOS's Unix-socket path limit in pytest's long temporary directory; Linux
  deployment behavior and the actual restart were verified separately.
- No future upstream image update has occurred yet; readback verifies the
  configured policy, not future GitLab-tag detection behavior.

No application production/staging service was restarted. No hooks were run.
