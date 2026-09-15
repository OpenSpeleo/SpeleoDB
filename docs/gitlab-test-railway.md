# Persistent GitLab for CI

## Intent and ownership

GitHub Actions and local development exercise real GitLab behavior. GitLab.com
applies hosted-service quotas to authenticated callers; a large integration
suite can consume project-creation quotas even when every token is correct.
CI therefore uses an always-on GitLab CE instance in Railway's `test`
environment. Its embedded PostgreSQL, Redis, and Gitaly run in one container.
Jobs do not install GitLab or repeat instance/group provisioning.

This is disposable test infrastructure, separate from SpeleoDB production
repositories and credentials. Public account registration is disabled. CI gets
a group-scoped token with API/read-repository/write-repository permissions;
the GitLab root password remains in the GitLab Railway service variables.

## Deployment

- Project: `speleoDB` (`247e5ad5-c8c4-41c3-9205-3014cc65df86`).
- Environment: `test` (`6d34d1bb-ba2e-4d36-ab57-216b936f8ce3`).
- Service: `GitLab` (`6dcb6ffb-5767-4526-a42b-aaa7c629e2f3`).
- Canonical URL: `https://gitlab-test.speleodb.org`.
- Docker build context: `compose/gitlab-railway/`.
- Image: official GitLab CE 19.3.2, pinned by digest in the Dockerfile.
- One replica in US East, sleeping disabled, 4 vCPU / 8 GB resource ceilings.
- Public TLS terminates at Railway; Omnibus NGINX listens on HTTP port 8080.
- Puma uses port 8081 for its optional loopback TCP listener. Workhorse reaches
  Puma through its Unix socket; leaving Puma on its default port 8080 prevents
  NGINX from binding the public listener.
- Deployment health check: `/users/sign_in`, with a 900-second initial timeout.
- Shutdown drain: 120 seconds, allowing the official entrypoint to stop services.

Deploy only this build context to the explicit test service:

```sh
railway up compose/gitlab-railway --path-as-root \
  --project 247e5ad5-c8c4-41c3-9205-3014cc65df86 \
  --environment 6d34d1bb-ba2e-4d36-ab57-216b936f8ce3 \
  --service 6dcb6ffb-5767-4526-a42b-aaa7c629e2f3
```

The repository's existing `.railway/railway.ts` manages production services.
Do not apply that production partial to this environment.

## Persistence

Railway mounts the 5 GB `gitlab-volume` at `/data`. The startup wrapper establishes:

| Omnibus directory | Persistent directory | Contents |
| --- | --- | --- |
| `/etc/gitlab` | `/data/config` | Configuration, encryption secrets, host keys |
| `/var/opt/gitlab` | `/data/gitlab` | PostgreSQL, Redis, repositories, application data |
| `/var/log/gitlab` | `/data/logs` | Application and service logs |

Persisting only repository/database data is insufficient: losing
`gitlab-secrets.json` breaks decryption of stored credentials on redeployment.
The wrapper seeds image directories only on first boot and preserves existing
volume contents on later boots. A missing Railway volume is a startup error.

The wrapper also removes stale runtime PID files and sockets before invoking
the official entrypoint. Omnibus's original cleanup does not follow the
`/var/opt/gitlab` symlink. The wrapper uses `find -H` with the same bounded
depth and filename selection, so an interrupted shutdown cannot leave a PID
file that prevents PostgreSQL or another bundled service from restarting.
Persistent database contents and configuration are preserved.

Runtime variables include `RAILWAY_RUN_UID=0`,
`RAILWAY_SHM_SIZE_BYTES=268435456`, `PORT=8080`, `GITLAB_EXTERNAL_URL`, and a
generated `GITLAB_ROOT_PASSWORD`. A short-lived `GITLAB_BOOTSTRAP_TOKEN` is used
only for initial administrative API provisioning, then revoked and removed.
Never store these secret values in source control or deployment logs.

## Instance policy and CI configuration

The post-reconfigure bootstrap applies these settings on every boot:

| Setting | Value | Intent |
| --- | --- | --- |
| `signup_enabled` | `false` | Only explicitly provisioned users can sign in |
| `project_create_limit` | `0` | Disable the per-user project-creation quota for integration tests |
| `group_create_limit` | `0` | Disable the per-user group-creation quota for disposable test groups |
| `deletion_adjourned_period` | `1` | Retain deleted test resources for the minimum one-day period |

These limits are disabled only on this dedicated test instance. Correct
credentials do not exempt callers from hosted GitLab quotas. Removing
redundant project-creation requests and keeping retries bounded remain useful
regardless of this instance policy.

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
effective configuration has not yet been independently verified. Metadata and
a successful remote smoke test do not establish which values a job loaded.

## Verification and maintenance

Store `GITLAB_GROUP_ID` as an Actions repository variable and read it with
`${{ vars.GITLAB_GROUP_ID }}` in both CI and scheduled cleanup. The test group's
ID is `3`; storing this ordinary identifier as a secret causes GitHub to mask
that digit throughout logs, including pytest's `3%` and `13%` progress output.
Keep the GitLab access token in Actions secrets. When migrating an existing
configuration, create the variable, publish both workflow updates, then remove
the obsolete group-ID secret so existing workflows never lose their namespace.

Deployment completion requires Railway `SUCCESS`, valid HTTPS, authenticated
API identity, project creation, and actual Git push/clone. Repeat those checks
after redeployment to prove persistence of repositories and credentials.
The public sign-in health check alone does not prove the CI token can write.

CI additionally runs `manage.py check_gitlab` before pytest. It prints the host,
authenticated username/ID and group path/ID, checks namespace consistency, then
creates and deletes a uniquely named private project. Authentication failures,
namespace mistakes, quota errors and missing write permissions stop the job.
No token values are printed.

An initial sample measured about 3.789 GB RAM and 0.603 GB of the 5 GB volume.
These are observations before sustained CI load, not capacity guarantees.
Monitor actual RAM/CPU and volume usage. Resource ceilings are not reservations;
GitLab's baseline memory consumption dominates idle cost. Increase volume
capacity before it fills, and keep test-project cleanup enabled. Before image
upgrades, take a volume backup and follow GitLab's required upgrade stops.

References: [GitLab container installation](https://docs.gitlab.com/install/docker/installation/),
[memory tuning](https://docs.gitlab.com/omnibus/settings/memory_constrained_envs/),
[Railway volumes](https://docs.railway.com/volumes),
[GitLab project rate limits](https://docs.gitlab.com/rate_limits/api/projects/).

## Deployment evidence

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
revoked with HTTP 204 afterward. The agent-owned smoke project was scheduled
for deletion with HTTP 202. The user's active CI token was preserved.

Full-suite validation remains pending. The local pytest run stalled around 77%
with four failures and one error and is being interrupted to inspect the
failures before targeted reruns. This is not a green full suite, and the
successful deployment does not establish a verified GitHub Actions run.

The rate-limit probe is a one-off administrative verification, not a recurring
CI test. It does not establish the historical GitLab.com threshold, nor cover
all possible HTTP 5xx or resource-lock conflict responses. See
[real integration test boundaries](ci-gitlab-testing.md).
