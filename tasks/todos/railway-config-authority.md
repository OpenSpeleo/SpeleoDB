# One Railway configuration authority

- [x] Compare the legacy TOML, existing IaC file, live service settings, and
      Railway's migration guidance.
- [x] Remove the deprecated `railway.toml` and its build-context exception.
- [x] Document `.railway/railway.ts` as the sole service configuration; retain
      `railpack.json` as the image-build recipe and preserve IaC ownership.
- [x] Validate the retained configuration in the running application container
      and review remaining references and the diff.
- [x] Record verification and the configuration-ownership lesson.

## Scope

The existing IaC file already contains the web deployment settings and also
manages the Celery worker, Beat, and Kanchi. Remove the redundant legacy file
without changing their commands or resource ownership. This cleanup does not
deploy application changes or resolve the separate Sentry TLS hypothesis.

## Review

Removed `railway.toml` and its `.dockerignore` exception. Updated agent
guidance, Railway setup/operations documentation, the asset architecture
reference, and the IaC ownership comment. All executable IaC settings and the
named partial remain unchanged; `railpack.json` continues to own image
construction.

Read-only Railway inventory confirmed the web service has an empty legacy config
path and the worker, Beat, and Kanchi have no custom config path. The staging
web service also has no custom config path and retains its independent dashboard
commands. No service has staged changes in these inspected settings. No
production configuration was applied and no deployment was performed.

`docker exec -w /app speleodb_local_django npm run typecheck:railway` passed.
`git diff --check` passed. Repository search found no remaining legacy Railway
TOML/JSON configuration files; active documentation references now describe
their removal or prohibition. The earlier historical Tailwind review prompt
remains historical. Independent read-only repository audit confirmed that the
IaC file already contains the meaningful legacy settings and no tests/scripts
depend on the deleted file. No new runtime tests are needed for this removal and
documentation-only change.
