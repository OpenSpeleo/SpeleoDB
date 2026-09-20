---
name: merge-dependabot
description:
  Fetch and locally merge every Git branch matching dependabot/* into the
  current branch, upgrade and regenerate all dependency locks once after all
  branches are merged, rebuild and test the Compose application, update prek
  hooks, and squash the verified result into one dependency-update commit. Use
  when consolidating Dependabot branches without pull requests; do not use for
  an ordinary single dependency edit.
---

# Merge Dependabot

Consolidate every `dependabot/*` branch on top of the currently checked-out
branch, but create the final commit only when the complete combined state passes
every repository-required check.

## Establish the safe boundary

1. Read the repository's `AGENTS.md` files, dependency-update documentation, and
   relevant lessons before changing Git state. Repository instructions are
   authoritative.
2. Before creating the repository-required task plan, require a completely clean
   tracked and untracked worktree. Do not stash, overwrite, or absorb
   pre-existing user changes. Treat the plan and review file created by this
   workflow as an explicit workflow-owned change, not as pre-existing work.
3. Treat the currently checked-out branch as the merge target. Require a named
   branch rather than detached `HEAD`, and do not switch branches.
4. Record the branch name and immutable starting SHA as `start_branch` and
   `start_sha`. Keep this SHA as the merge-rollback and final-squash boundary.
5. Fetch every `dependabot/*` branch from every configured Git remote using the
   explicit `+refs/heads/dependabot/*:refs/remotes/<remote>/dependabot/*`
   refspec with pruning. Enumerate and snapshot every matching local branch
   under `refs/heads/dependabot/` and every fetched remote-tracking branch under
   `refs/remotes/<remote>/dependabot/` with
   `git for-each-ref --sort=refname --format='%(refname) %(objectname)'`. Record
   every full refname and exact head SHA. If none exist, stop and report that
   there is nothing to merge. Do not inspect or use pull requests or their refs
   anywhere in this workflow.

Do not push or delete local or remote branches unless the user separately
requests it.

## Merge every branch before locking

Process all recorded branch refs in deterministic refname order. Branches
updating GitHub Actions, Docker, and other non-lockfile dependencies are part of
the same required set. Do not run uv, npm, or another package manager inside
this per-branch loop.

For each branch ref:

1. Verify the ref still points to its recorded head SHA. If it moved, stop,
   refetch and resnapshot the complete branch set, and restart verification from
   the changed set. If that SHA is already an ancestor of `HEAD`, record the ref
   as already included and continue. Otherwise record `pre_merge_sha = HEAD`.
2. Start `git merge --no-ff --no-commit <dependabot-ref>`.
3. Resolve every merge conflict before continuing:

   - Preserve the combined intent of manifest, configuration, workflow, and
     source changes. Do not discard one dependency update merely to finish the
     merge.
   - If `uv.lock` or `package-lock.json` conflicts, always take `--ours`, stage
     the file, and continue. Do not inspect, combine, or regenerate either lock
     during the merge; both are provisional until the single consolidated
     regeneration phase.
   - Inspect the resolved staged diff, stage the resolutions, and finish the
     merge commit with its default message.

If a conflict cannot be resolved coherently, run `git merge --abort`, verify
`HEAD == pre_merge_sha`, and stop. Do not hide a failed branch or proceed to the
final squash. Otherwise continue merging without running package-manager lock,
install, update, or upgrade commands.

After the loop, verify every recorded branch head is an ancestor of `HEAD`. Only
then begin dependency resolution.

## Upgrade and regenerate locks once

Run each applicable package-manager workflow once against the combined result of
all merges:

- For Python, run `uv lock --upgrade`, followed by `uv lock --check` and
  `uv tree --outdated --depth 1`. Document every direct dependency held back by
  an explicit compatibility constraint; do not relax a known compatibility bound
  merely to make the report empty.
- For npm, run `npx --yes npm-check-updates -u --peer`, then generate a fresh
  `package-lock.json` independently of `node_modules` and its hidden lockfile.
  Use `npm install --package-lock-only --ignore-scripts` from a temporary
  working directory containing the final combined `package.json` and repository
  npm configuration, then copy the result back. Verify that the root dependency
  graph matches `package.json`, package keys are only the root and
  `node_modules/...`, and every registry package retains `resolved` and
  `integrity` metadata. The canonical filename is `package-lock.json`; do not
  invent `packages.lock`. Then run `npm install` from the repository root and
  require it to succeed before rebuilding containers. Revalidate the manifest,
  lock graph, and registry metadata after the install.
- If another package-manager manifest is actually present, run its complete
  repository-documented upgrade and lock workflow once. Do not introduce a
  package manager merely to satisfy this checklist.

Resolve dependency-solver conflicts against the complete merged manifest set.
Preserve every compatible update and the repository's documented compatibility
bounds. If the combined graph cannot be resolved without discarding an intended
update or violating a required bound, stop and report the concrete blocker.

The dependency state is stable only when every applicable upgrade, lock, and
consistency command succeeds and the final manifests and lockfiles agree.

## Rebuild, update hooks, and verify

Only after the dependency state is stable, rebuild the existing Compose project;
never start a second verification stack. For SpeleoDB, use `local.yml` and
recreate the current application with
`docker compose -f local.yml up -d --build --remove-orphans`. Wait until the
required services are healthy, including the repository's container startup
`npm ci` against the finalized `package-lock.json`. Confirm the test container
is `speleodb_local_django` with the repository mounted at `/app`.

Run the hook autoupdate inside the application container:

```bash
docker exec -w /app speleodb_local_django prek autoupdate
```

Inspect every revision change. Keep duplicated tool versions such as Ruff and
djLint aligned with project dependency pins. If this changes a package manifest
or lockfile, return to the consolidated lock phase, stabilize every affected
lock, and rebuild Compose again before testing.

## Require a green final state

Run the complete test suites inside the already-running application container:

```bash
docker exec -w /app speleodb_local_django npm run test:js
docker exec -w /app speleodb_local_django make test-py
```

For SpeleoDB's Python suite, preserve the GitLab creation-audit environment and
inspect the generated `.artifacts/gitlab/<run-id>/summary.json` and
`events.jsonl`. A budget violation, unresolved creation, or cleanup failure is a
failed suite even if pytest itself exited successfully. Record the actual
creation POST and successful-creation counts plus cleanup result.

Then run the all-files hook gate inside the same container:

```bash
docker exec -w /app speleodb_local_django prek run -a
```

If hooks modify files, inspect the changes, rerun both complete in-container
suites against that final tree, and rerun the containerized all-files hook gate.
Repeat until the hook run is green and makes no changes. Stop without squashing
on any failed build, service health check, test, audit, or hook.

## Squash only after verification

Refetch the explicit `dependabot/*` refspec from every configured remote and
re-enumerate all matching local and remote-tracking branch namespaces
immediately before squashing. If a branch appeared or disappeared, or a recorded
head SHA changed, return to the merge-all phase, then run one new consolidated
upgrade-and-lock phase followed by every build, test, audit, and hook gate. Do
not inspect pull requests.

Complete the repository task file's review section and make a temporary commit
for any remaining workflow-owned documentation. Then verify every recorded
branch head is an ancestor of the current pre-squash tip, the current branch is
still `start_branch`, `start_sha` is an ancestor of `HEAD`, and the worktree is
clean. Record `pre_squash_tip`.

Squash exactly the range after `start_sha`:

```bash
git reset --soft "$start_sha"
git commit -m '[Dependency Update]'
```

Verify all of the following:

- `HEAD^` is exactly `start_sha`.
- `git rev-list --count "$start_sha..HEAD"` is exactly `1`.
- The commit subject is exactly `[Dependency Update]`.
- The final commit's tree is identical to `pre_squash_tip`.
- The worktree is clean.

If the squash commit fails, restore the recorded `pre_squash_tip` before doing
anything else. Do not push the final commit without explicit authorization.

Report the merged, already-included, skipped, or failed branch refs; their
recorded head SHAs; lockfile commands and constraints; Compose rebuild status;
full test results; GitLab audit counts when applicable; final prek result;
starting SHA; and final commit SHA.
