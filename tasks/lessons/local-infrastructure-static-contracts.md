# Local Infrastructure Static Contracts

## Lesson

Canonical local infrastructure names must remain explicit when the repository
owns them. Do not derive fixed development or test bucket names from runtime
settings: a typo or unexpected environment override can silently provision the
wrong resource while appearing successful.

Likewise, a Docker Compose service with `restart: "no"` is not a once-ever
initializer when another service lists it under `depends_on`. Compose schedules
the completed container again on a later `up` operation.

## Rules

- Keep the canonical development and test bucket names visible in the
  provisioning loop and document them as part of the local infrastructure
  contract.
- Add a regression test proving an `AWS_STORAGE_BUCKET_NAME` override cannot
  change the buckets provisioned by the local command.
- Keep create-once setup jobs out of normal application dependencies.
- Profile-gate explicit initialization jobs and invoke them only during initial
  bucket setup or an intentional reconfiguration/migration.
- Use `docker compose --dry-run` when reviewing whether a supposedly one-shot
  service will be scheduled by normal startup.
- With host networking, do not add Docker `EXPOSE` or Compose `ports` entries
  solely for VS Code. Use `forwardPorts` in `devcontainer.json` when reopening
  in a Dev Container, and workspace-level remote auto-forwarding when running
  plain Docker Compose through Remote SSH or Tunnels.
