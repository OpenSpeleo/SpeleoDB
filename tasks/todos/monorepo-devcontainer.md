# Monorepo devcontainer integration

## Plan

- [x] Reuse `local.yml`, the Django image, `/entrypoint`, and `/start` unchanged.
- [x] Keep the web checkout mounted at `/app` while exposing the monorepo at
      `/workspace` to the development container.
- [x] Supply the local GitLab settings required by Django from the tracked local
      environment file.
- [x] Verify migrations, the Vite watcher, and Django startup on port 8000.

## Review

The root devcontainer composes on top of this subtree rather than duplicating
its services. During the smoke test, Django correctly reached `/start` but the
tracked `.envs/.django` lacked the GitLab values required unconditionally by
`config/settings/base.py`. The added values target the existing local GitLab
service and are development-only.

The root feature image built successfully. An isolated Compose smoke stack ran
the existing `/start`, applied migrations, installed the standalone JavaScript
environment, started the Vite watcher, and returned HTTP 200 from Django on
port 8000 inside the service. The smoke stack was removed afterward without
touching the developer's existing stopped `speleodb_local_*` containers.
