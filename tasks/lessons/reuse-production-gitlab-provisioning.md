# Use the production repository provisioning flow in test fixtures

The user explicitly rejected special GitLab naming and initialization logic in
the repository pool. Use `GitlabManager.create_or_clone_project()` so UUID
names, creation, retries, and initial commits follow the same path as the
application. Keep test-specific allocation and lease restoration around that
call; do not reimplement provisioning or customize author identities to make
commit hashes unique. Identical empty commits can legitimately share a SHA
across repositories.
