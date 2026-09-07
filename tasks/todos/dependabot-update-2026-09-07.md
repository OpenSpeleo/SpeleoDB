# Dependency Update — 2026-09-07

## Objective

Consolidate every open Dependabot update targeting `dev`, refresh all supported
dependency graphs to the newest mutually compatible releases, verify the full
application/tooling contract, and deliver one local `[Dependency Update]`
commit. Preserve runtime behavior and record any dependency that cannot be
updated with its concrete compatibility blocker.

## Plan

- [x] Read repository guidance and dependency-update lessons.
- [x] Fetch `origin` and identify the authoritative set of open Dependabot PRs
      targeting `dev`.
- [x] Inspect the pending branch diffs and adversarially assess upgrade risks,
      compatibility constraints, and required validation.
- [x] Merge every open `dependabot/*` branch locally, resolving overlapping
      manifest and lockfile changes into one coherent graph.
- [x] Run `npx --yes npm-check-updates -u --peer`, accept every compatible npm
      update, and regenerate `package-lock.json` independently of the installed
      tree while preserving registry integrity metadata.
- [x] Run `uv lock --upgrade`, accept every compatible Python update, and record
      exact blockers for any release that the resolver cannot select.
- [x] Remediate compatibility failures exposed by the upgraded type packages:
      handle DRF mapping-versus-list request data at the narrowest shared
      boundary, update changed fixture/file generic annotations, and add or run
      focused regression coverage before accepting the new stubs.
- [x] Confirm that Cargo and Bun updates are not applicable (no manifests or
      lockfiles are present); otherwise run their complete update workflows.
- [x] Update every stale `prek` hook revision and validate the resulting hook
      environments, including aligned ruff and djLint tool versions.
- [x] Update `AGENTS.md` with the durable dependency-update procedure and an
      explicit `Can't update A until X Y Z is satisfied` blocker log.
- [x] Update dependency architecture documentation with ownership, lockfile
      reproducibility, verification strategy, and compatibility rationale.
- [x] Run a clean dependency install/check, production asset build, all
      JavaScript tests and lint, the full Python test suite, and `prek run -a`.
- [x] Have the adversarial principal-engineer sub-agent review the consolidated
      diff and verification evidence; fix every actionable finding and rerun
      affected checks.
- [x] Review the final diff for unrelated changes, add results below, and squash
      the complete change set into one `[Dependency Update]` commit.

## Review

- Merged all 41 open Dependabot heads targeting `dev` and consolidated their
  overlapping dependency graphs locally.
- Updated every compatible direct npm and Python dependency. Django 6.1, orjson
  3.12, and pyproj 3.8 remain at the newest compatible versions because of the
  resolver-proven blockers documented in `AGENTS.md`.
- Regenerated a portable 232-node npm lock and a 187-package uv lock. The npm
  graph has no temporary paths, missing registry integrity metadata, unapproved
  install scripts, or audit findings. Cargo and Bun are not present.
- Adapted to the DRF 3.18 typing contract with one object-body guard. Read-only
  callers reuse parsed data; mutation sites explicitly copy it. Top-level JSON
  arrays now receive a deterministic HTTP 400, and the upgraded GitPython retry
  tests mock only the command under test.
- Updated all stale pre-commit hook revisions, kept ruff/djLint aligned with the
  project dependencies, and targeted django-upgrade at Django 6.0.
- Verified clean installs on Node 22, 24, and 26; Vite production and watcher
  builds; JavaScript lint and all 977 JavaScript tests; a Python 3.14.7
  application-image build; mypy across 560 source files; the full Python suite
  with 4,064 passed, 157 skipped, and 43 subtests passed; and `prek run -a`.
- The adversarial review confirmed all 41 heads were represented and found no
  unresolved code-level issue after lock portability, request-shape, Git test,
  and dependency-blocker corrections.
