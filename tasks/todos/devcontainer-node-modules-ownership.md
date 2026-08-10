# Devcontainer Node Modules Ownership

## Plan

- [x] Reproduce and identify the ownership mismatch on the shared
      `/app/node_modules` volume.
- [x] Make the one-shot root setup service initialize or migrate the volume to
      `dev-user` ownership only when necessary.
- [x] Run Django application services as `dev-user` so npm and Vite cannot
      recreate root-owned files.
- [x] Add regression coverage for service users, shared volume wiring, and the
      ownership initializer.
- [x] Update local-development documentation and capture the correction lesson.
- [x] Recreate the affected services and verify ownership, `npm ci`, Vite,
      tests, lint, typing, Compose rendering, and rebuild persistence.

## Review / Results

The shared Node dependency volume had two conflicting writers: the webserver's
root `/start` process installed dependencies and created Vite temporary files,
while the devcontainer terminal ran builds as `dev-user`. The Docker build also
accepted host `node_modules`, so a fresh image/volume could begin with the wrong
platform and owner.

The application services now run as `dev-user`; only setup remains root. Setup
checks the volume-root UID/GID and performs a recursive ownership migration only
for a fresh or legacy volume. Host dependencies are excluded from the build
context, the named volume uses `nocopy: true`, and the image's fallback mount
point is owned by `dev-user`. Dev Containers keep the fixed UID/GID 1000
contract instead of rewriting only the interactive service.

Live verification repaired the existing volume without deleting it. `npm ci` and
`npm run build:assets` then passed as `dev-user`, with no files owned by another
user. The rebuilt webserver runs as `dev-user`, its watcher-created `.vite-temp`
remains UID/GID 1000, and its HTTP endpoint returns 200.

A separate temporary Compose project proved the fresh-volume and rebuild paths:
root setup initialized the empty volume, a first `dev-user` container installed
and built successfully, and a second fresh container reused the same volume and
built again. A complete ownership scan remained clean after both runs. The
temporary containers, networks, and volumes were removed afterward.

Verification:

- Compose infrastructure tests: `11 passed`.
- Full JavaScript suite as `dev-user`: `50 passed` files, `933 passed` tests.
- JavaScript lint as `dev-user`: passed.
- Focused Ruff check/format and mypy: passed.
- Shell syntax, Compose rendering, image build, Vite build, HTTP smoke test,
  bounded ownership scans, JSONC validation, and `git diff --check`: passed.
