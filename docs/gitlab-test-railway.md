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

The settings below describe the service's operating configuration. The startup
files are tracked locally; Railway owns the image, resources, domain, and update
policy. Read back those settings when operating the service rather than treating
this document as evidence of current live state.

- Project: `speleoDB`.
- Environment: `test`.
- Service: `GitLab`.
- Canonical URL: `https://gitlab-test.speleodb.org`.
- Connected Docker image source: `gitlab/gitlab-ce:latest`.
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
GitHub repository or a custom image build. Image-update checks depend on the
connected image source. Do not use `railway up` on this directory for normal
updates, as that uploads another custom build.

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
updates. Verify the configured policy separately from an actual image update; a
policy readback alone does not prove an upgrade completed.

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

## Verification and maintenance

Configure `GITLAB_HTTP_PROTOCOL=https`,
`GITLAB_HOST_URL=gitlab-test.speleodb.org`, and the private CI group's name and
ID as a consistent set. Store `GITLAB_GROUP_ID` as an Actions repository
variable, read with `${{ vars.GITLAB_GROUP_ID }}` in CI and manual cleanup.
Treating an ordinary numeric group ID as a secret can mask unrelated log digits.
Keep `GITLAB_TOKEN` in Actions secrets, with `api`, `read_repository`, and
`write_repository` scopes limited to the test group. Verify effective job
configuration through authenticated preflight; secret metadata cannot establish
which value a job loaded.

When moving the group ID from a secret to a variable, create the variable first,
publish both workflow consumers, and verify they read the variable before
removing the obsolete secret. Workflows still reading the secret must retain
their namespace configuration throughout the transition.

Deployment completion requires Railway `SUCCESS`, valid HTTPS, authenticated API
identity, project creation, and actual Git push/clone. Repeat those checks after
redeployment to prove persistence of repositories and credentials. The public
sign-in health check alone does not prove the CI token can write.

CI runs `manage.py check_gitlab --read-only` before pytest. It prints the host,
authenticated username/ID and group path/ID, and checks namespace consistency
without creating a project. Authenticated create/delete verification belongs to
pytest's `write-check` allocation within the nine-project budget. No token
values are printed. See [real GitLab integration tests](ci-gitlab-testing.md).

### Manual cleanup settings

`.github/workflows/cleanup_gitlab.yml` runs only through `workflow_dispatch` and
passes `--older-than-hours 24`. Preserve that age filter while branch jobs can
overlap. Unrestricted `make wipe_gitlab_test` requires that no tests use the
group; normal pytest cleanup owns only the current invocation's repositories.

`GITLAB_HOST_URL` is a hostname, such as `gitlab-test.speleodb.org`, without a
scheme or trailing slash. The client adds the protocol from Django settings.
`make wipe_gitlab_test` explicitly selects `config.settings.test`: local GitLab
uses HTTP, while this remote hostname uses HTTPS. The default `manage.py`
settings are local settings, which force HTTP and must not determine the remote
cleanup protocol.

Railway redirects HTTP to HTTPS with 301. Reads can appear to work, but
python-gitlab rejects redirected writes, even after a DELETE received 202 from
GitLab. Cleanup reports a specific redirect instruction and includes exception
type/HTTP status for API failures without printing tokens or raw server response
bodies.

Regression coverage invokes the actual Makefile target against a disposable
subgroup, independently of the caller's Django settings. It checks deletion,
repeated cleanup, and invalid-token failure through the CLI. Cleanup skips
projects already marked for deletion; GitLab otherwise rejects a second DELETE
with HTTP 400 during the retention period. Verification never wipes the shared
CI group. See
[the SDK's redirect guidance](https://python-gitlab.readthedocs.io/en/stable/api-usage.html#gitlab-gitlab-class).

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
