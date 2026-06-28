# Node and Vite Tooling

## Intent

SpeleoDB has one root Node workspace and one first-party asset graph. Vite
8.1.0 compiles Tailwind, route CSS, application ES modules, and shared chunks;
Django remains the only HTML and static-file server. The repository does not
run Vite's development server, proxy, HMR client, or HTML transformer.

Node 22.12 or newer is required. Production images use Node 24. Exact direct
compiler dependencies are `vite@8.1.0`, `@tailwindcss/vite@4.3.1`, and
`tailwindcss@4.3.1`. Forms and typography remain pinned at `0.5.11` and
`0.5.20`. The lockfile's only approved direct install script is the optional
`fsevents@2.3.3` package; audit approvals whenever the graph changes.

## Asset graph

`frontend_common/entries.json` is the committed logical-entry registry. Vite
uses it as its complete input set and Django uses the same names when rendering
manifest-backed tags. Entries preserve route boundaries: one Tailwind sheet,
separate public/private shell styles, route/modal/map styles, one small
bootstrap, and lazy route controllers. Shared imports become shared chunks.

Production writes hashed files and `.vite/manifest.json` under
`speleodb/common/static/speleodb/vite/`. Development writes stable entry names,
source maps, and a refreshed manifest to the same ignored directory. Django
serves those files; a browser refresh picks up a completed disk rebuild.

All SpeleoDB-authored CSS/JS belongs in the graph as an entry, transitive
module, test, or intentionally removed source. Templates load it with
`vite_styles`, `vite_preload`, and `vite_script`. Vendored/CDN libraries and
Django-generated `url_reverse.js` remain outside Vite.

## Commands

- `npm run build:clean`: remove Vite and obsolete Tailwind/esbuild output.
- `npm run build:assets`: one production Vite build.
- `npm run build`: clean, then build all assets.
- `npm run dev`: one `vite build --watch --mode development` process.
- `npm start`: alias for `npm run dev`.
- `npm run pre-commit`: the same clean production build contract.
- `npm run test:assets-watch`: isolated watcher invalidation matrix.
- `npm run lint:js` and `npm run test:js`: source quality gates.

The watcher test mirrors sources under the operating-system temporary
directory and reuses the installed dependency tree. It proves imported CSS
change/deletion, Tailwind source additions, shared-module invalidation,
route-controller invalidation, and unrelated-route output stability.

Tailwind 4.3.1's Vite plugin accumulates discovered utility candidates during
one watch process. Removing a template class therefore may leave harmless CSS
until restart; imported CSS deletion is removed correctly. Final evidence must
always stop the watcher, run `npm run build`, and verify the served manifest
hash. A running watcher is development convenience, never release evidence.

## Django and deployment

The Django manifest reader reloads by manifest mtime in DEBUG and caches in
production. Missing, malformed, unsafe, duplicate, or wrong-type entries fail
loudly. DEBUG/test may fall back to registry-derived stable names before the
first watcher build. URLs pass through Django static storage, preserving local
serving and S3/CloudFront behavior.

Railpack installs Node 24 and runs `npm ci && npm run build` while constructing
the image. The runtime retains generated assets and manifest but not
`node_modules`. Railway pre-deploy runs only migrations and `collectstatic`,
because pre-deploy filesystem changes are not persisted. SPA serving is
disabled and Gunicorn/Django remains the start command.

When updating tooling, run clean installs on Node 22 and 24, audit pending
scripts, run the complete build/lint/test suite, exercise watcher invalidation,
and verify `collectstatic` plus production module MIME/CORS behavior.
