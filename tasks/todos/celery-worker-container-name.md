# Explicit local Celery worker container name

- [x] Set the worker container name using the existing instance-prefix
      convention.
- [x] Update the local operations documentation for the single-worker
      constraint.
- [x] Validate Compose names and rename the existing container without
      restarting it.
- [x] Record verification in `tasks/todo.md`.

Verification: resolved Compose JSON assertions passed inside the running Django
container for both worker and Beat names. Docker inspection confirmed the
renamed worker remains running with the same container ID and start time. Diff
whitespace validation passed. No application behavior changed.
