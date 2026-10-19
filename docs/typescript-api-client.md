# Generated TypeScript API client

SpeleoDB browser code uses `@speleodb/api` for every first-party API operation,
including allauth browser authentication, private v2 resources, public GIS and
OGC, file processing, and exports. The package owns endpoint paths, parameter
encoding, request bodies, response types, and HTTP decoding. Its generated
operations come from the composed Django/OpenAPI contract; they are never edited
by hand.

The web application owns session credentials, CSRF, UI state, permissions,
retry/polling decisions, and display models. Keeping these policies outside the
SDK allows the mobile application to use the same operations with its own native
transport and token storage. `frontend_common/api/client.ts` is the browser
adapter. `frontend_private/static/private/ts/map_viewer/api.ts` is a map-facing
facade over concrete generated operations; it does not build URLs or implement a
second HTTP client.

## Calling an operation

Import the generated function and DTO from the package root. The browser adapter
binds a same-origin client and obtains the current CSRF token at request time,
first from the page's hidden Django input, then from the `csrftoken` cookie. It
does not capture an old token during module initialization.

```ts
import { v2ProjectsList } from "@speleodb/api";
import { apiData, webApiOptions } from "../api/client.ts";

const projects = await apiData(v2ProjectsList(undefined, webApiOptions()));
```

Use the actual generated signature for the selected release. DRF operations
declare their optional `format` query parameter, so their query object precedes
request options even when the caller does not need a query. Pass `undefined` in
that position. Other operations retain the signature generated from their own
declared parameters. Generated functions always receive `webApiOptions()` in the
options position. Controllers supply callbacks to shared forms instead of
passing endpoint strings. Template context contains resource identity and UI
configuration, not API transport instructions.

Use generated request/response DTOs at the network boundary. Local map state may
add coordinates, derived permission flags, cache state, or incomplete unsaved
records. Name and document these as display models; derive their wire fields
from SDK types with `Pick`, `Omit`, or `Partial`. Do not maintain another copy
of a server DTO or cast an incompatible response to silence a compiler error. A
changed generated type can reveal a real schema or consumer defect.

## Encoding and files

Where an endpoint accepts several media types, generation produces separate
`WithJson`, `WithFormData`, and `WithUrlEncoded` variants. Choose the variant
that matches the endpoint and UI. Operations with one request media type retain
the base operation name. Form helpers convert DOM values into the generated
request type; a DOM `FormData` is not an untyped escape hatch.

Creation and PATCH forms have different required fields. Resource creation uses
the selected operation's generated body union: a note requires nonempty text and
forbids uploaded files; a photo, video, or document requires a file. Resource
editing uses `PatchedStationResourceRequest` and preserves fields omitted from
the form. Disabled controls are absent from `FormData(form)`, so an edit form's
disabled resource-type selector must not become a required creation field. Empty
text inputs remain explicit updates; absent file inputs preserve existing files.

JSON operations receive typed objects. Multipart operations receive typed
objects containing `File`/`Blob` values. The generated client constructs the
multipart body and the browser creates its boundary. Do not set a multipart
`Content-Type` header manually. JSON field and enum validation at a form
boundary remains useful because an HTML input always produces a string.

Read each encoding variant's input type: a JSON field that accepts an object in
an `application/json` request can require a JSON-encoded string in a form
request. Serialize that field explicitly when the generated form type requires
`string`. Preserve the difference between omission and explicit `null`; the
generator records the server's form-field null representation. Do not replace
null with an empty value or skip it to make a request compile.

The SDK uses fetch by default. Passing `onUploadProgress` or `onUploadComplete`
selects its XHR transport. The web `uploadWithProgress` helper accepts a
generated-operation callback, supplies those callbacks and an `AbortSignal`, and
returns an `AbortController`. It owns progress UI and error presentation; it no
longer owns XHR, URL construction, or JSON decoding. Cancellation must settle
the pending operation once and release UI state.

A server or transport failure after an upload may leave publication uncertain.
The import UI preserves its existing check-before-retry behavior for that case;
a transport failure must not automatically resubmit a file. Project upload's
explicit `304` result means the content is unchanged and is handled before
ordinary successful response unwrapping. Upload progress reaching 100% means
transfer completion, not that server processing or publication has finished.

Binary endpoints return a `Blob` according to their generated response media
metadata. A controller can create an object URL for a download and revoke it
after use. Keep server-provided filenames and HTML output escaped. Generated URL
builders are appropriate for browser-managed download links, but ordinary API
data reads and writes use generated operation functions.

## Status, errors, and deadlines

The SDK resolves HTTP responses, including non-2xx statuses. Check `kind` before
relying on a documented DTO:

```ts
const response = await operation(/* typed arguments */, webApiOptions());
if (response.kind === 'documented' && response.status === 304) {
    // Endpoint-specific unchanged-content behavior.
}
```

`apiData` accepts only a documented 2xx response and otherwise raises
`ApiRequestError`. The error retains `status`, `data`, and response headers for
field validation and UI messages. An unexpected status or content type retains
unknown data; never treat it as a success DTO. Transport errors, aborts,
deadlines, and decoding failures reject independently of HTTP status. Always
release disabled controls/spinners in completion/finally paths, including when
request construction fails synchronously.

Allauth signup deliberately treats its documented `401` response as a valid
signup outcome requiring the next authentication step. That decision belongs to
the auth controller, not the shared `apiData` helper. Similarly, `304` handling
belongs to the project upload controller. Do not generalize either exception to
unrelated endpoints.

The web adapter sets `timeoutMs: null`, preserving the browser's previous lack
of a total request deadline. Large uploads and server-side conversion can take
longer than the SDK's default ten seconds; the app has no established finite
deadline that covers both transfer and processing. Explicit `AbortSignal`
cancellation still applies with no deadline. Do not remove this override when
updating the package, or ordinary uploads will inherit the SDK default.

Set `timeoutMs` explicitly where a flow has an existing deadline. Export and
GeoJSON polling retain their cancellation, retry budgets, visibility handling,
and page teardown. SDK timeouts are per request and do not replace the UI's
whole polling lifecycle. Thread `signal` through the operation options so
navigation and superseding searches can cancel obsolete work.

## Credentials and non-API network boundaries

First-party browser operations use same-origin session credentials and CSRF.
They do not persist a new API token in local storage. Public GIS and OGC calls
use the generated public operation and its token parameter. Their explicit
cookie/redirect policy must remain intact; XHR cannot enforce cookie omission or
redirect refusal, so these requests use fetch.

Some network traffic is intentionally outside the SDK contract: signed object
storage URLs for survey GeoJSON, GPS tracks and GIS layers; tile resources;
static SVG icons; the external Nominatim geocoder; and the externally hosted
feedback form. These URLs are not first-party API endpoints. Do not attach the
session client or CSRF header to them. Keep signed URLs opaque and maintain the
existing origin/credential/redirect rules. Browser navigation to an export or
OpenAPI documentation page is also distinct from an authored data request.

`scripts/audit-api.ts` checks authored browser TypeScript with the TypeScript
AST and symbol information. It rejects raw API URLs and raw HTTP entrypoints,
including aliases, and has narrow, explained exceptions for those asset and
external-service boundaries. Adding a new first-party feature should not add a
new exception. The reviewed raw-network boundaries are:

| Owner                                   | Network purpose              |
| --------------------------------------- | ---------------------------- |
| `controllers/feedback.ts`               | External feedback submission |
| `controllers/xls2compass.ts`            | Nominatim location search    |
| `map_viewer/components/context_menu.ts` | Static SVG icons             |
| `map_viewer/map/layers/gps.ts`          | Signed GPS object data       |
| `map_viewer/map/layers/gis.ts`          | Signed GIS object data       |
| `map_viewer/map/layers/survey.ts`       | Signed survey GeoJSON data   |
| `map_viewer/map/sources.ts`             | Renderer tile data           |

The server-rendered export links and copyable GIS integration URLs remain Django
reversals. They are browser navigation or URLs for external GIS clients; they do
not define TypeScript data operations.

Do not bypass the audit by hiding a URL in another variable or calling the SDK's
low-level request primitive from a controller.

## Updating the package and consumers

The package maintainer guide owns schema export, route inventory, contract
coverage, generation, package tests, and release packaging. In a standalone
checkout, use the published package's README and maintainer documentation. In
the monorepo these live under `packages/typescript/api/docs/`. The Django
contract remains the source of truth; if implementation and export disagree,
correct the owning view/serializer and its contract test before regenerating. Do
not edit generated operation or model files in the installed package. Web's root
`OpenAPI.yaml` is the sole checked-in schema. The SDK exports
`openapi-source.json` with its producer revision and SHA-256; neither consumers
nor the npm package need another YAML copy. See
[the backend contract guide](api-contract.md) for export freshness and
provenance comparison, and the SDK maintenance guide for pinned remote or
explicit local generation inputs.

For a consumer upgrade:

1. Review the generated operation/model diff and the endpoint contract evidence,
   including error statuses, authentication, nullability, media types, enum
   values, pagination, and empty/binary responses.
2. Upgrade the exact `@speleodb/api` version in the standalone web manifest and
   refresh its standalone Bun lock. The monorepo overlay resolves the live
   workspace for development; it must not replace the published version with a
   relative path in the standalone application.
3. Update imports, typed request construction, documented status handling, and
   display-model adaptation together. Preserve timeout, cancellation, progress,
   signup and unchanged-upload behavior. Fix schema drift at the backend when
   the generated type contradicts an observed endpoint.
4. Run runtime/development/tooling typechecks, frontend lint, the API boundary
   audit, the frontend suite, template/source audits, and the production Vite
   build. Run affected Django contract tests and live upload integration tests
   for changed file or endpoint behavior.
5. Verify a standalone frozen install against the published exact release and
   the monorepo integration graph. An unpublished package is a release gate;
   workspace success does not prove that a standalone clone can install it.

### Updating from 0.2 to 0.3

The corrected contract introduces an optional query position before request
options for DRF operations. Preserve the full argument order: path arguments,
body when present, query, then options. Use `undefined` for an unused query;
otherwise keep existing filters in the query object. This applies to GET and
DELETE as well as request-body methods. Passing `webApiOptions()` in the query
position can lose the browser client, CSRF, cancellation, or progress behavior.
Typecheck each caller rather than inserting arguments into authentication or OGC
operations whose signatures differ.

Two media declarations also change the web imports:

- GIS-layer creation now uses `v2GisLayersCreate`, replacing
  `v2GisLayersCreateWithFormData`, because its required file permits only
  multipart input.
- Experiment-record JSON creation now uses
  `v2StationsExperimentRecordsCreateWithJson`, replacing
  `v2StationsExperimentRecordsCreate`, because the contract separately describes
  JSON and form input.

Full experiment-record writes require a measurement-date string; build that
field explicitly instead of casting a generic dynamic object to the generated
body. Continue sending scalar values through the JSON variant. Form-created
records can return nonempty string arrays, including the submitter email, so
read/display types derive from `ExperimentRecord['data']`. Keep the scalar
`ExperimentValues` write type separate from `ExperimentReadValue`. Existing
form-created records can reject subsequent PUT/PATCH because the server
preserves that submitter array; do not imply that accepting an array response
makes it a valid write value.

Review the other newly expressed input requirements at their owning form
boundary: geometry updates require `expected_revision`, resource creation must
satisfy its note/file union, and select experiment fields require options.
Preserve existing revision conflict handling and partial-edit omission
semantics. Do not relax these generated requirements with casts or optional DTO
copies.

Run web checks from `/app` in the existing application container, following
`AGENTS.md`, for example `bun run typecheck`, `bun run lint:frontend`,
`bun run audit:api`, `bun run test:frontend`, and `bun run build`. The real HTTP
frontend fixtures exercise generated requests rather than mocking the SDK. The
browser-adapter regression holds real fetch and XHR responses for eleven
seconds, verifies completion and caller cancellation, and checks finite per-call
overrides without replacing clocks. `tests/browser/resource-edit.spec.ts` uses
the rendered viewer edit form to save a note and a replacement document through
real Django endpoints. It checks the PATCH body, independently reads saved
values and S3 bytes, and reloads the viewer to verify persistence. Run it
through the Django browser wrapper with the configured test S3 service and
bucket; `tests/browser/resource_fixtures.py` supplies isolated station/resource
rows and removes their uploaded objects afterwards. No application HTTP response
or browser transport is replaced. Manually constructing a create-shaped
`FormData` does not exercise disabled edit controls. The Django view tests parse
the rendered controller JSON and verify resource identities, permission flags,
form configuration, and navigation. Update those assertions alongside controller
context changes; an API URL appearing elsewhere in the page does not prove that
a form targets the correct entity. The shared test parser also rejects duplicate
controller JSON keys. The Django upload integration test covers stored
artifacts, authenticated CSRF, progress/cancellation, and ambiguous failure
behavior against real endpoints.

Generated operations do not automatically introduce retries or caching. Keep
existing request coalescing, state caches, bulk list reads, and explicit refresh
behavior in their owning UI modules to avoid extra network work.
