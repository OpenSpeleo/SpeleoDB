# Persistent GitLab for CI

## Intent and ownership

GitHub Actions and local development exercise real GitLab behavior. GitLab.com
applies hosted-service quotas to authenticated callers; a large integration
suite can consume project-creation quotas even when every token is correct. CI
therefore uses an always-on GitLab CE instance in Railway's `test` environment.
Its embedded PostgreSQL, Redis, and Gitaly run in one container. Jobs do not
install GitLab or repeat instance/group provisioning.

This is disposable test infrastructure, separate from SpeleoDB production
repositories and credentials. Public account registration is disabled. CI gets a
group-scoped token with API/read-repository/write-repository permissions; the
GitLab root password remains in the GitLab Railway service variables.

## Deployment

- Project: `speleoDB` (`247e5ad5-c8c4-41c3-9205-3014cc65df86`).
- Environment: `test` (`6d34d1bb-ba2e-4d36-ab57-216b936f8ce3`).
- Service: `GitLab` (`6dcb6ffb-5767-4526-a42b-aaa7c629e2f3`).
- Canonical URL: `https://gitlab-test.speleodb.org`.
- Connected Docker image source: `gitlab/gitlab-ce:19.3.2-ce.0`.
- Start command: `/bin/bash /data/speleodb/start`.
- Automatic updates: patches only, daily 09:00–10:00 UTC (04:00–05:00 Cancún).
- Startup/configuration sources: `compose/gitlab-railway/`, installed on the
  persistent volume under `/data/speleodb`.
- One replica in US East, sleeping disabled, 4 vCPU / 8 GB resource ceilings.
- Public TLS terminates at Railway; Omnibus NGINX listens on HTTP port 8080.
- Puma uses port 8081 for its optional loopback TCP listener. Workhorse reaches
  Puma through its Unix socket; leaving Puma on its default port 8080 prevents
  NGINX from binding the public listener.
- Deployment health check: `/users/sign_in`, with a 900-second initial timeout.
- Shutdown drain: 120 seconds, allowing the official entrypoint to stop
  services.

The service pulls the official image directly from Docker Hub. Its source, start
command, and update policy are configured in Railway. It does not require a
GitHub repository or a custom image build. The original uploaded Dockerfile
deployment could not receive Railway image-update checks; the connected image
replaces that deployment path. Do not use `railway up` on this directory for
normal updates, as that uploads another custom build.

The Railway-specific startup files live on the volume so official image updates
retain them. Their environment variables are:

```text
GITLAB_OMNIBUS_CONFIG=from_file('/data/speleodb/gitlab.rb')
GITLAB_POST_RECONFIGURE_SCRIPT=gitlab-rails runner /data/speleodb/bootstrap.rb
GITLAB_DISABLE_OPENSSH=true
```

For changes to those scripts, install the reviewed files on `/data/speleodb`
before restarting the service. Preserve the existing file permissions: `start`
is executable (0755), and the Ruby files are readable (0644). A volume restore
must include this directory alongside the GitLab data and secrets.

Railway's image-update policy is configured as:

```json
{
  "type": "patch",
  "schedule": [
    { "day": 0, "startHour": 9, "endHour": 10 },
    { "day": 1, "startHour": 9, "endHour": 10 },
    { "day": 2, "startHour": 9, "endHour": 10 },
    { "day": 3, "startHour": 9, "endHour": 10 },
    { "day": 4, "startHour": 9, "endHour": 10 },
    { "day": 5, "startHour": 9, "endHour": 10 },
    { "day": 6, "startHour": 9, "endHour": 10 }
  ]
}
```

Patch-only updates avoid jumping over GitLab's required minor-version upgrade
stops. Minor/major upgrades require checking the upgrade path and completed
background migrations. Railway documents volume backups before automatic image
updates. Configuration readback proves the policy is enabled; a future upstream
release is needed to observe an actual automatic version update, including
Railway's handling of GitLab's `-ce.0` suffix.

The repository's existing `.railway/railway.ts` manages production services. Do
not apply that production partial to this environment.

## Persistence

Railway mounts the 5 GB `gitlab-volume` at `/data`. The startup wrapper
establishes:

| Omnibus directory | Persistent directory | Contents                                          |
| ----------------- | -------------------- | ------------------------------------------------- |
| `/etc/gitlab`     | `/data/config`       | Configuration, encryption secrets, host keys      |
| `/var/opt/gitlab` | `/data/gitlab`       | PostgreSQL, Redis, repositories, application data |
| `/var/log/gitlab` | `/data/logs`         | Application and service logs                      |

Persisting only repository/database data is insufficient: losing
`gitlab-secrets.json` breaks decryption of stored credentials on redeployment.
The wrapper seeds image directories only on first boot and preserves existing
volume contents on later boots. A missing Railway volume is a startup error.

The wrapper also removes stale runtime PID files and sockets before invoking the
official entrypoint. Omnibus's original cleanup does not follow the
`/var/opt/gitlab` symlink. The wrapper uses `find -H` with the same bounded
depth and filename selection, so an interrupted shutdown cannot leave a PID file
that prevents PostgreSQL or another bundled service from restarting. Persistent
database contents and configuration are preserved.

Runtime variables include `RAILWAY_RUN_UID=0`,
`RAILWAY_SHM_SIZE_BYTES=268435456`, `PORT=8080`, `GITLAB_EXTERNAL_URL`, and a
generated `GITLAB_ROOT_PASSWORD`. A short-lived `GITLAB_BOOTSTRAP_TOKEN` is used
only for initial administrative API provisioning, then revoked and removed.
Never store these secret values in source control or deployment logs.

## Instance policy and CI configuration

The post-reconfigure bootstrap applies these settings on every boot:

| Setting                     | Value   | Intent                                                               |
| --------------------------- | ------- | -------------------------------------------------------------------- |
| `signup_enabled`            | `false` | Only explicitly provisioned users can sign in                        |
| `project_create_limit`      | `0`     | Disable the per-user project-creation quota for integration tests    |
| `group_create_limit`        | `0`     | Disable the per-user group-creation quota for disposable test groups |
| `deletion_adjourned_period` | `1`     | Retain deleted test resources for the minimum one-day period         |

These limits are disabled only on this dedicated test instance. Correct
credentials do not exempt callers from hosted GitLab quotas. Removing redundant
project-creation requests and keeping retries bounded remain useful regardless
of this instance policy.

The user created the private CI group `github-ci` (ID `3`) and owns the active
group token named `github CI` (ID `4`), created at 21:30:17 UTC. Its scopes are
`api`, `read_repository`, and `write_repository`. The earlier agent-created CI
token was revoked. The intended GitHub test configuration is:

- `GITLAB_HTTP_PROTOCOL=https`
- `GITLAB_HOST_URL=gitlab-test.speleodb.org`
- `GITLAB_GROUP_NAME=github-ci`
- `GITLAB_GROUP_ID=3`
- `GITLAB_TOKEN` stored as the group-token secret

The user updated the GitHub CI environment manually. GitHub secret metadata
confirms host/group updates at 21:27 UTC and the token update at 21:30:43 UTC.
The API does not return secret plaintext, and a GitHub Actions run against that
effective configuration has not yet been independently verified. Metadata and a
successful remote smoke test do not establish which values a job loaded.

## Verification and maintenance

Store `GITLAB_GROUP_ID` as an Actions repository variable and read it with
`${{ vars.GITLAB_GROUP_ID }}` in both CI and scheduled cleanup. The test group's
ID is `3`; storing this ordinary identifier as a secret causes GitHub to mask
that digit throughout logs, including pytest's `3%` and `13%` progress output.
Keep the GitLab access token in Actions secrets. When migrating an existing
configuration, create the variable, publish both workflow updates, then remove
the obsolete group-ID secret so existing workflows never lose their namespace.

Deployment completion requires Railway `SUCCESS`, valid HTTPS, authenticated API
identity, project creation, and actual Git push/clone. Repeat those checks after
redeployment to prove persistence of repositories and credentials. The public
sign-in health check alone does not prove the CI token can write.

CI additionally runs `manage.py check_gitlab` before pytest. It prints the host,
authenticated username/ID and group path/ID, checks namespace consistency, then
creates and deletes a uniquely named private project. Authentication failures,
namespace mistakes, quota errors and missing write permissions stop the job. No
token values are printed.

### Scheduled cleanup settings

`GITLAB_HOST_URL` is a hostname, such as `gitlab-test.speleodb.org`, without a
scheme or trailing slash. The client adds the protocol from Django settings.
`make wipe_gitlab_test` explicitly selects `config.settings.test`: local GitLab
uses HTTP, while this remote hostname uses HTTPS. The default `manage.py`
settings are local settings, which force HTTP and must not determine the remote
cleanup protocol.

Railway redirects HTTP to HTTPS with 301. Reads can appear to work, but
python-gitlab rejects redirected writes, even after a DELETE received 202 from
GitLab. Run 35033828799 hit exactly this configuration mismatch. Cleanup now
reports a specific redirect instruction and includes exception type/HTTP status
for API failures without printing tokens or raw server response bodies.

Regression coverage invokes the actual Makefile target against a disposable
subgroup, independently of the caller's Django settings. It checks deletion,
repeated cleanup, and invalid-token failure through the CLI. Cleanup skips
projects already marked for deletion; GitLab otherwise rejects a second DELETE
with HTTP 400 during the retention period. Verification never wipes the shared
CI group. See
[the SDK's redirect guidance](https://python-gitlab.readthedocs.io/en/stable/api-usage.html#gitlab-gitlab-class).

An initial sample measured about 3.789 GB RAM and 0.603 GB of the 5 GB volume.
These are observations before sustained CI load, not capacity guarantees.
Monitor actual RAM/CPU and volume usage. Resource ceilings are not reservations;
GitLab's baseline memory consumption dominates idle cost. Increase volume
capacity before it fills, and keep test-project cleanup enabled. Before image
upgrades, take a volume backup and follow GitLab's required upgrade stops.

References:
[GitLab container installation](https://docs.gitlab.com/install/docker/installation/),
[memory tuning](https://docs.gitlab.com/omnibus/settings/memory_constrained_envs/),
[Railway volumes](https://docs.railway.com/volumes),
[GitLab project rate limits](https://docs.gitlab.com/rate_limits/api/projects/),
[Railway image updates](https://docs.railway.com/deployments/image-auto-updates),
[GitLab upgrade paths](https://docs.gitlab.com/update/upgrade_paths/).

## Deployment evidence

### Official image source migration

The September 15 source migration created volume backup
`2804168c-5d0e-4157-8e3c-7b3eaf971315`, then deployed the official Docker Hub
image as deployment `8fd607fd-bfd5-43f7-b9f3-9bb2c0ac18e8`. Railway reported
SUCCESS at 23:24:05 UTC. The source, start command, and daily patch-update
window were read back from the live service configuration.

HTTPS, the root password, CI group/token records, and an existing repository
commit survived. A temporary token for the CI bot successfully authenticated,
read the existing commit, created a disposable private project, read its README,
and scheduled deletion. The temporary token was revoked. The persistent startup
files matched their repository hashes, and both startup filesystem tests passed
in Docker. The application production/staging services were unaffected.

### Original provisioning

Verified during the September 2026 setup:

- Deployment `b011d7cb` reached Railway `SUCCESS`; HTTPS and authenticated API
  access succeeded.
- Actual HTTPS Git push and a fresh clone preserved project `2` at commit
  `683c8420d5528ed23f158cd93ac4125cfbf700c6`.
- A temporary private group and bot exercised GitLab's real project-creation
  limiter. The first POST returned 201, then the bounded client received actual
  429 responses: one request with `obey_rate_limit=False` and two requests with
  a two-attempt budget. Response hooks verified the bot token on real requests.
  No HTTP responses or SDK methods were substituted.
- That probe changed `project_create_limit` to `1` and enabled
  `namespace_create_rate_limit` only for its bot user. Recovery completed after
  a cached feature-flag read delayed the first cleanup check. The explicit flag
  is gone, the temporary bot token is revoked, and the instance creation quotas
  are back at `0`. The temporary group follows GitLab's deletion retention.
- The administrative bootstrap token was revoked with HTTP 204; reuse returned
  HTTP 401. Its Railway variable was removed. The CI group token remains
  separate from administrative credentials.

Final deployment `3debd5be-5a0b-4299-af87-e00e6b0ad39a` reached `SUCCESS` at
21:38:47 UTC. It contains the stale-PID cleanup and boot-time quota/retention
settings. Root login and the private repository survived the redeploy. A fresh
HTTPS clone after restart matched the original commit SHA and file bytes,
verifying repository and credential persistence across this deployment.

That final clone used a separate temporary verification group token, which was
revoked with HTTP 204 afterward. The agent-owned smoke project was scheduled for
deletion with HTTP 202. The user's active CI token was preserved.

Full-suite validation remains pending. The local pytest run stalled around 77%
with four failures and one error and is being interrupted to inspect the
failures before targeted reruns. This is not a green full suite, and the
successful deployment does not establish a verified GitHub Actions run.

The rate-limit probe is a one-off administrative verification, not a recurring
CI test. It does not establish the historical GitLab.com threshold, nor cover
all possible HTTP 5xx or resource-lock conflict responses. See
[real integration test boundaries](ci-gitlab-testing.md).
