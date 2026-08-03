# Compass Sidecar Release Link Resolution

## Intent

The public download page links directly to the latest Windows MSI for Compass
Sidecar. Release metadata comes from the Sidecar project's Tauri-generated
`latest.json`, but the URL in that updater document is not guaranteed to be a
browser download URL. SpeleoDB therefore treats `latest.json` as untrusted
release metadata and resolves its Windows URL into a validated GitHub release
link before exposing it in page context.

This boundary has two goals:

- Keep the download button working with both URL variants emitted by the
  Sidecar release workflow.
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
- The path belongs to
  `/OpenSpeleo/speleodb_compass_sidecar/releases/download/` and ends in `.msi`.
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

The resolved payload contains the Windows URL, version, and optional publication
date. It uses Django's cache for one hour by default. A cached payload is reused
only when its Windows URL is either a valid direct Sidecar MSI link or the
configured releases-page fallback. An old cached asset API URL or any invalid
cached URL is ignored so that SpeleoDB performs a fresh resolution instead of
serving a non-browser or unsafe link.

On a cache miss, a direct URL requires one request for `latest.json`; an asset
API URL requires one additional small JSON metadata request. A valid cache hit
requires no network request. SpeleoDB never downloads or buffers the MSI, so
request cost and memory use are independent of installer size.

If `latest.json`, the GitHub asset lookup, payload parsing, or URL validation
fails, SpeleoDB logs a warning and returns the configured GitHub releases page
with version `latest` and no publication date. That fallback is cached using the
same timeout to avoid repeatedly calling a failing upstream during page loads.
The separate “View all releases” link remains available on the page.

## Testing and Operational Verification

Automated tests should use mocked responses for deterministic coverage of:

- A valid direct MSI URL, which must be returned without an asset API request.
- A valid asset API URL resolved through `browser_download_url`.
- Rejection of wrong repositories, schemes, hosts, path forms, nonnumeric asset
  IDs, credentials, query strings, fragments, and non-MSI download URLs.
- Missing or malformed GitHub metadata and invalid resolved download URLs.
- Valid direct and fallback cache hits, plus fresh resolution for stale API or
  invalid cached URLs.
- Network failures at either request and the releases-page fallback behavior.

The live GitHub test verifies that the current `latest.json` shape resolves to
an HTTPS download URL under the Sidecar repository and ending in `.msi`.
Operational checks should also open the public download page, confirm the
Windows button targets that browser URL, and verify that following it downloads
the installer rather than displaying GitHub API JSON. If releases begin falling
back unexpectedly, inspect application warnings and compare the current
`latest.json` URL shape with the two allowlisted forms before broadening the
trust boundary.
