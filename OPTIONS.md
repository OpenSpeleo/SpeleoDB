# GitLab connection settings

SpeleoDB reads GitLab connection settings from environment variables in
`config/settings/base.py`. They identify the server and group that own project
repositories.

| Variable            | Meaning                                                                                      |
| ------------------- | -------------------------------------------------------------------------------------------- |
| `GITLAB_HOST_URL`   | GitLab hostname, optionally including a port. Omit the URL scheme and trailing slash.        |
| `GITLAB_TOKEN`      | API access token for the GitLab account used by SpeleoDB. This is a secret token, not a URL. |
| `GITLAB_GROUP_NAME` | Full namespace path of the group that contains project repositories.                         |
| `GITLAB_GROUP_ID`   | Numeric ID of that same group.                                                               |

For an existing hosted or self-hosted GitLab instance, create an API token for
the SpeleoDB account through that instance's access-token settings. Create or
select the group that will own the repositories, then record that same group's
full namespace and numeric ID. Store the token in the deployment's secret
environment configuration; local Compose manages separate development and test
credentials.

The settings module selects the HTTP protocol separately through
`GITLAB_HTTP_PROTOCOL`. Production uses HTTPS; local development and test
settings handle the local GitLab service.

The local Compose setup provisions separate development and test groups and
writes their connection settings to the corresponding ignored environment files.
See [local services](docs/local-object-storage.md) and
[GitLab testing](docs/ci-gitlab-testing.md) for their ownership and isolation.

From the running application container, the read-only connection check verifies
authentication and that the group ID and namespace identify the same group:

```bash
python manage.py check_gitlab --read-only
```

The command without `--read-only` also creates and deletes a repository. Test
connections use `--settings config.settings.test` and the isolated test
credentials.
