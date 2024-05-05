# Server OPTIONS

Here are the OPTIONS that you need to declare in the database for the server to function

- `GITLAB_HOST_URL="https://gitlab.com/"`<br>
The url to the GIT platform being used. Either self-hosted or cloud service.

- `GITLAB_TOKEN="https://<git_host>.com"`<br>
A token can be obtained at:
  - <https://gitlab.com/-/user_settings/personal_access_tokens>>

- `GITLAB_GROUP_NAME=<group_name>`<br>
Provide a GITLAB group to use as a common place for all projects: <https://gitlab.com/groups/new>

- `GITLAB_GROUP_ID=<group_id>`<br>
Provide the GITLAB group ID: <https://gitlab.com/groups/new>
