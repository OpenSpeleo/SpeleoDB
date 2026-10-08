# Compass Sidecar Release Link Resolution

## Intent

The public download page links directly to the latest Windows MSI for Compass
Sidecar. Release metadata comes from the Sidecar project's Tauri-generated
`latest.json`, but the URL in that updater document is not guaranteed to be a
browser download URL. SpeleoDB therefore treats `latest.json` as untrusted
release metadata and resolves its Windows URL into a validated GitHub release
link before exposing it in page context.

This boundary has two goals:

- Keep the download button working with both URL variants emitted by the Sidecar
  release workflow.
- Prevent a compromised or malformed metadata document from turning the public
  page into an arbitrary external redirect.

## Tauri and GitHub URL Variants

SpeleoDB reads `platforms.windows-x86_64-msi.url` from `latest.json`. Two forms
are supported:

1. A direct browser URL such as
   `https://github.com/OpenSpeleo/speleodb_compass_sidecar/releases/download/<tag>/<asset>.msi`.
   This is validated and returned without another request.
2. A GitHub release asset API URL such as
   `https://api.github.com/repos/OpenSpeleo/speleodb_compass_sidecar/releases/assets/<asset-id>`.
   This URL is suitable for Tauri's updater, but opening it in a browser returns
   asset metadata rather than the installer. SpeleoDB fetches that metadata and
   uses its `browser_download_url` after validating it as a direct URL.

The asset lookup explicitly requests GitHub JSON metadata with
`Accept: application/vnd.github+json` and API version `2022-11-28`. It does not
request `application/octet-stream`, follow a binary download flow, or proxy the
MSI through SpeleoDB.

## URL Trust Boundary

Accepted direct links must satisfy all of these conditions:

- Scheme is `https` and host is exactly `github.com`.
- The path belongs to `/OpenSpeleo/speleodb_compass_sidecar/releases/download/`
  and ends in `.msi`.
- Decoded path segments contain no dot traversal, backslashes, or ASCII control
  characters that a client could normalize into a different route.
- The URL has no embedded username or password, query string, or fragment.

Recognized asset API links are similarly restricted:

- Scheme is `https` and host is exactly `api.github.com`.
- The path is exactly
  `/repos/OpenSpeleo/speleodb_compass_sidecar/releases/assets/<asset-id>`, where
  the asset ID contains digits only.
- The URL has no embedded username or password, query string, or fragment.

An API response is not trusted merely because it came from GitHub. Its
`browser_download_url` must pass the direct-link validation above. Other hosts,
repositories, schemes, path shapes, file extensions, and decorated URLs are
rejected.

## Cache, Failure, and Request Behavior

The resolver returns the Windows URL, version, and optional publication date, or
`None` when release information is unavailable. Both results use Django's cache
for one hour by default. Cached direct URLs must still pass validation. Legacy
cached releases-page fallbacks are treated as empty results; stale asset API
URLs or invalid cached URLs trigger fresh resolution.

On a cache miss, a direct URL requires one request for `latest.json`; an asset
API URL requires one additional small JSON metadata request. Both requests and
all retries share a one-second monotonic deadline. Each request's timeout is
capped by the remaining budget. Connection errors, timeouts, and HTTP 429, 500,
502, 503, and 504 are retried with exponential delays starting at 100 ms, then
200 ms and 400 ms when time remains. No retry starts after the deadline, and no
sleep is taken if it would consume the remaining budget. Permanent HTTP errors,
invalid JSON, and failed payload or URL validation are not retried.

When resolution fails, the resolver logs one warning and caches `None`, avoiding
repeated requests during an upstream outage. The download view owns
presentation: an empty result displays the GitHub releases-page link with
version `latest` and no publication date. The separate “View all releases” link
remains available. A valid cache hit requires no network request. SpeleoDB never
downloads or buffers the MSI, so request cost and memory use are independent of
installer size.

## Testing and Operational Verification

`CompassSidecarReleaseFetchTests` uses controlled responses and a monotonic
clock to test successful extraction, caching, URL validation, retryable and
permanent failures, the exponential delay sequence, and the budget shared by
release and asset requests. Tests also verify that exhaustion returns and caches
`None` without further requests, and that the view renders its releases-page
fallback.

The live GitHub check remains in the ordinary suite without an offline skip. It
validates a direct MSI URL and metadata when available, or the explicit cached
empty result after a failed lookup. It does not require GitHub to be available
for the application contract to pass. Deterministic success tests independently
require valid metadata, so a broken resolver cannot pass merely by always
returning `None`.

Run these checks inside the existing application container:

```sh
docker exec -w /app speleodb-monorepo-django pytest frontend_public/tests/test_views.py
```

Operational checks should also open the public download page, confirm the
Windows button targets that browser URL, and verify that following it downloads
the installer rather than displaying GitHub API JSON. If releases begin falling
back unexpectedly, inspect application warnings and compare the current
`latest.json` URL shape with the two allowlisted forms before broadening the
trust boundary.
