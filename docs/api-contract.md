# Maintaining the SpeleoDB API contract

`OpenAPI.yaml` at the repository root is the canonical public HTTP contract used
by `@speleodb/api`. It is generated from this Django application and is the sole
checked-in schema. The TypeScript SDK repository,
[OpenSpeleo/SpeleoDB-TS-API](https://github.com/OpenSpeleo/SpeleoDB-TS-API),
records the backend revision and exact SHA-256 in `openapi-source.json`, then
generates its client and DTOs from that verified source. It contains no second
YAML file. Do not independently serialize, format, or hand-edit the canonical
artifact. Fix the backend declarations and regenerate.

The SDK's
[maintenance guide](https://github.com/OpenSpeleo/SpeleoDB-TS-API/blob/master/docs/maintenance.md)
explains its pinned generator, runtime transport, package versioning, standalone
checks, and web/mobile updates. This document explains the backend half,
including how to establish that declarations match real HTTP behavior.

## Scope and source ownership

The composed contract contains current `/api/v2/` endpoints (including the four
OGC API Features families), `/api/health/`, both configured allauth mounts
(`/_allauth/` and `/api/auth/`), Git smart HTTP under `/git/`, the three
`/.well-known/` discovery endpoints, and `/api/schema/`. Authentication's `v1`
is allauth's current protocol version. The obsolete SpeleoDB application mirror
`/api/v1/` is deliberately excluded and must not generate SDK operations.

Authentication's `/api/auth/` compatibility mount resolves to the same views,
but its operations have distinct `auth_alias_` identifiers and require actual
requests at that mount as coverage evidence. HTML account pages, DRF's HTML
API-browser representation, admin pages, documentation UI, static assets,
presigned storage URLs, and external downloads are outside the machine API
contract. HTML errors that machine clients can receive, such as browser CSRF
failures, are included. A signed URL returned by an API remains a URL; it is not
rewritten to a generated endpoint. The operation inventory counts explicitly
implemented GET/POST/PUT/PATCH/DELETE handlers. Framework-provided HEAD/OPTIONS
negotiation does not produce additional SDK functions; no separately implemented
business handler is excluded by that rule.

OGC's six old bare-SHA collection routes return `410 Gone` with replacement
`Link` headers. Their URL templates collide with the current geometry-specific
collection templates in OpenAPI, although Django distinguishes their converters.
The canonical operations therefore explicitly declare that `410` response and
explain the deprecated converter variant. They are not silently dropped and the
current operation is not marked deprecated. The OGC service document itself has
its own `200`/`304` operation.

| Concern                                                        | Authoritative source                                                                                                    |
| -------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Paths, converters and supported methods                        | Django URL modules and actual view methods                                                                              |
| First-party requests, successes and errors                     | View `extend_schema` declarations, serializers, `schema_auto.py`, `schema_extensions.py`, and `schema_domain.py`        |
| Configured authentication routes and DTOs                      | Installed django-allauth exporter under current settings, with explicit corrections in `schema.py` and `schema_auth.py` |
| OGC discovery, collections, features and parameters            | `speleodb/gis/ogc_openapi.py`                                                                                           |
| Git protocol, well-known discovery and schema export           | `speleodb/api/schema_protocol.py`, checked against their actual handlers                                                |
| Composition, namespacing, origin and nullable references       | `speleodb/api/schema.py`                                                                                                |
| Canonical artifact generation/checking                         | `export_api_schema` management command                                                                                  |
| Independent route coverage                                     | `speleodb/api/schema_inventory.py` and `test_api_contract.py`                                                           |
| Actual rendered response validation                            | `speleodb/testing/api_contract.py` and pytest contract plugin                                                           |
| Required operation evidence and observed status/media branches | `verify_api_contract_coverage` and `docs/api-contract-coverage.json`                                                    |

## Environment and reproducible export

Use the repository's Python 3.14 environment and committed `uv.lock`:

```sh
uv sync --extra local --frozen
uv run python manage.py export_api_schema
uv run python manage.py export_api_schema --check
```

Normal Django configuration must be available, using the same ignored
environment files as application development. Do not copy credentials into YAML,
scripts, or CI output. Export inspects the configured application; it does not
seed a database, create a GitLab project, upload artifacts, or make production
API requests.

Use PostgreSQL database configuration, as CI does, even though export does not
connect to the database. DRF derives model integer bounds from the configured
database backend; SQLite test defaults produce different bounds. When exporting
with `config.settings.test`, set `TEST_DATABASE_URL` to the PostgreSQL
connection configuration instead of relying on the test environment's SQLite
default.

In the monorepo, run application commands from `/app` in the existing Django
container so its pinned environment and mounted sources are used:

```sh
docker exec -w /app speleodb-monorepo-django \
  python manage.py export_api_schema

docker exec -w /app speleodb-monorepo-django \
  python manage.py export_api_schema --check \
  --compare-source /workspace/packages/typescript/api/openapi-source.json
```

For a reviewable draft outside the checkout:

```sh
docker exec -w /app speleodb-monorepo-django \
  python manage.py export_api_schema --output /tmp/OpenAPI.yaml

docker cp speleodb-monorepo-django:/tmp/OpenAPI.yaml /tmp/OpenAPI.yaml
```

`--output` changes only the destination. `--check` regenerates into an OS
temporary directory and fails when the destination is missing or differs,
without rewriting it. `--compare-source PATH` reads the SDK's JSON provenance
record and requires its `sha256` to equal the hash of the freshly generated
bytes. It does not hash a possibly stale destination instead. The record must
contain a 64-character lowercase SHA-256 and `revision`, either a full
40-character lowercase backend commit or `null` during unpublished work. This
comparison checks the digest; it does not fetch or prove availability of that
revision. Standalone SDK generation and release require the real published
revision and verify its downloaded bytes separately.

Whitespace, line endings, and terminal newlines affect the digest. Missing,
malformed or mismatched source records fail without rewriting the destination or
the record. The command prints a SHA-256 digest for review and always enables
schema validation, warning-as-error behavior, and English schema text. It runs
the equivalent of:

```sh
python manage.py spectacular --format openapi --lang en \
  --validate --fail-on-warn --file OpenAPI.yaml
```

The public document uses origin-relative `servers: [{url: /}]` and complete
mounted paths. SDK callers configure a server origin, not an `/api/v2` base
path. Exported paths must not depend on localhost, the current request host, or
a developer's storage endpoint. Repeated exports under the same configured
contract must produce the same bytes.

## Why OpenAPI 3.0.3

DRF-spectacular, the installed allauth exporter, and the focused OGC document
all produce OpenAPI 3.0.3. Composition retains their dialect, including OGC's
advertised `conf/oas30`, instead of claiming a version conversion that has not
been performed. A future move to 3.1 requires upgrading and testing all three
sources together.

Component names from authentication and OGC are prefixed with `Auth` and `OGC`.
Every local reference is rewritten exactly once, including references in shared
nested dictionaries. Duplicate paths/components and mixed dialects fail export.
Allauth client placeholders are expanded only for configured browser/app
clients. Its signup schema comes from the configured signup form (`name`,
`country`, email and password), and its authenticated user object is the allauth
user representation, not the first-party profile endpoint DTO.

In OpenAPI 3.0, putting `nullable` next to an `allOf` reference does not make
the referenced object's own constraints nullable. Composition expresses this as
an explicit non-null schema alternative plus a null alternative. This retains
every required field on the non-null object and permits the actual `null`
response. Do not work around nullable failures by dropping required properties.

## Changing an endpoint

1. Inspect the Django resolver entry, permission classes, parsers, and every
   return and exception branch in the view, including helpers it calls. Record
   the actual method, path parameters, query/header parameters, request media,
   statuses, body, response media and headers. A serializer on `GenericAPIView`
   is not proof that the handler uses it for either direction.
2. Fix the runtime behavior first if a defect is demonstrated. Keep server-owned
   values server-owned: a read-only serializer field ignores values inserted
   into input data, so pass provenance such as `created_by` explicitly to
   `save()`. Use creation-specific serializers for both request validation and
   schema declarations when creation requires fields that updates may omit.
3. Declare transport differences at the source. Keep existing `operation_id`
   values stable: they are generated client API names. A change from one object
   to an array must not accidentally rename an established operation from
   `retrieve` to `list`. New operations need unique, descriptive IDs.
4. Add or update meaningful integration cases that exercise actual requests and
   inspect rendered responses. Include the new success and relevant failure
   branches. Check missing fields, null values, empty arrays, and permission
   denial.
5. Regenerate and review the artifact, then run endpoint tests with contract
   enforcement and inspect coverage. Update the SDK source record and generated
   client together after the backend revision is available upstream. Compile
   both consumers to expose assumptions that no longer match the contract.

For explicit response envelopes, use concrete serializer fields and the helpers
in `schema_helpers.py`. A list response needs `many=True`; a GeoJSON response
needs a Feature or FeatureCollection shape, not the model's ordinary serializer.
A polymorphic station response must declare both surface and subsurface output.
When a serializer overrides `to_representation`, examine its output rather than
assuming its model fields describe the wire.

Input optionality and output optionality differ. Model defaults can make input
fields optional while those fields are always present in output. Conversely,
project coordinates and selected context-dependent fields can genuinely be
omitted. Nullable means a present key can contain `null`; it does not mean the
key may be absent. Context-annotated fields require endpoint-specific attention.
For example, cylinder installation creation requires a non-null `project`;
PUT/PATCH may omit it to preserve the existing association. Test an otherwise
valid creation with only that field missing, so unrelated validation errors
cannot hide a database constraint failure.

When a route-specific subclass delegates to a shared handler, retain the whole
handler's response contract. Project downloads at the current revision and at a
specified commit share binary success and JSON 400/403/404/422/500 declarations.
A valid commit without the requested source file returns 422 on either route.
Changing the operation ID must not drop inherited error statuses.

Use numeric or string alternatives where DRF accepts both, such as decimal
coordinate inputs. Do not copy database storage types into response types when
`to_representation` emits numbers. Dates with a custom presentation format are
strings with that format, not RFC 3339 `date-time`. Choice fields may accept
case-insensitive names while emitting canonical names or numeric values;
describe each direction separately.

For permissions, distinguish the response DTO from the mutation body. A user
permission mutation accepts a user email and level; a revocation still has a
DELETE body. Team membership uses a role and project team permission uses a team
UUID. `schema_auto.py` supports explicitly declared DELETE inputs because the
upstream generator otherwise ignores those bodies.

## Multipart, files, dynamic data and streaming

A file upload is `multipart/form-data`. Repeated project `artifact` fields form
an array of binary parts. File bytes cannot be represented as an ordinary
URL-encoded string. Optional uploads on JSON endpoints need their actual
non-file representation, including nullable clears where the runtime supports
them. DRF JSONField values in HTML forms are JSON-encoded strings; JSON request
bodies contain JSON values. Do not copy the same binary schema across every
default parser media type.

Required uploaded files make JSON and URL-encoded representations unavailable;
they do not become optional merely because those parsers are installed. A
resource creation declaration separates note text from the required file for
photos, videos and documents. A body is required only when every supported input
variant requires it. Required geometry revisions remain required on PATCH even
though ordinary partial serializers omit other required fields.

HTML forms have no native null value. A form property marked
`x-drf-null-as-empty: true` accepts an empty value as DRF `None`; the SDK
serializes an explicit `null` that way. A nullable text field that also allows
blank text cannot distinguish null from an empty string in a form. Its form
schema excludes null; use JSON for that clear. An omitted property stays
omitted, especially on PATCH. JSONField form values are already JSON strings:
send `"null"` to represent JSON null, without encoding that string a second
time. File fields expose only binary multipart uploads or the supported
empty/null clear representation in other media.

For JSON encoded inside a text field, `x-json-schema` documents the decoded
structure while the wire schema remains a string. This applies to form JSON
fields and the DMP doctor configuration. `x-normalized-schema` describes the
internal validated representation when spreadsheet inputs undergo conversion; it
must not replace the original row shape sent by callers.

Do not infer support for nested values from a view's parser list. Initial sensor
arrays are accepted in JSON; ordinary repeated form strings are not nested
serializer objects. Landmark bulk transfer/deletion likewise accepts its UUID
list in JSON. GIS view creation/full replacement requires a JSON project array;
partial updates can also use forms for their scalar fields. Those media
differences are part of generation. The repeated multipart project artifacts are
real files and have a minimum of one item. Spreadsheet tool inputs describe the
original rows; the internal Compass model is a transformed representation with
computed station pairs and magnetic declination. Compass input requires latitude
and longitude. Cross-row and date-relative rules remain runtime validation, with
descriptions in the schema.

File extension validators constrain uploaded filenames. Their patterns and
filename length limits are recorded as `x-filename-pattern`,
`x-filename-minLength`, and `x-filename-maxLength`, never as constraints on
binary file contents. Download responses contain signed URLs, often with query
strings, so those filename regexes do not constrain the returned URL. A binary
response needs its actual content type and a binary schema. Some Excel endpoints
intentionally return `application/octet-stream` while others return the
spreadsheet MIME type. Preserve those distinctions and verify
Content-Disposition, filenames and empty/not-modified branches.

Experiment records have dynamically configured field UUIDs as keys. Their values
are constrained by the selected experiment at runtime. Geometry schemas describe
the supported LineString/Polygon structure; geographic bounds, polygon closure,
self-intersection and area limits still need behavioral tests. OpenAPI is not a
replacement for data-dependent business validation.

A response observer must validate rendered bytes, not `response.data`: rendering
changes decimals, dates and files. OGC streams use GeoJSON MIME types; the
validator registers JSON deserializers for those media types and the OpenAPI
service document. Media parameters such as charset/version are preserved by HTTP
and do not change JSON syntax. Stream inspection must leave the stream
consumable by the test.

Git POST operations accept raw protocol bytes, not JSON or form fields. Their
responses can report a protocol rejection with HTTP 200; the Git client must
interpret the packet stream. Keep the declared packet MIME types and binary body
semantics. The validator accepts empty bytes only through the normal media
deserializer and schema validation: an empty text or binary representation can
be valid, while empty JSON remains invalid.

## Contract verification

Run the owning endpoint suite first. Keep reports in an external temporary path:

Use the configured PostgreSQL backend for the authoritative contract audit. The
private `.envs/test.env` may select SQLite; set `TEST_DATABASE_URL` in the test
process to the existing provisioned PostgreSQL connection when needed. Pass that
value privately and never print its credentials. SQLite behavior checks remain
useful, but do not export the release contract from its test settings: DRF
derives some integer bounds from the database backend, and those bounds differ.
CI supplies PostgreSQL through its configured environment.

```sh
docker exec -w /app speleodb-monorepo-django pytest \
  speleodb/api/v2/tests/test_user.py \
  --api-contract-report=/tmp/user-contract.json --api-contract-enforce
```

The independent resolver matrix checks that every supported path/method has
exactly one generated operation, instantiates every route with valid converter
values, and validates its real anonymous response. Authentication aliases
resolve to the same views and return the same response status/media as their
canonical paths, but observations retain their actual paths and operation IDs.
Inventory follows DRF/allauth handler classes wherever mounted, with explicit
exclusions for the obsolete SpeleoDB v1 mirror and HTML documentation UI; it
does not infer completeness from a list of expected API prefixes:

```sh
docker exec -w /app speleodb-monorepo-django pytest \
  speleodb/api/v2/tests/test_api_contract.py \
  --api-contract-report=/tmp/route-contract.json --api-contract-enforce
```

Then run the existing integration suites with the observer enabled. Their
fixtures provide authenticated CRUD, actual uploads/storage, exports,
permissions, pagination, OGC filtering and conditional responses, and
domain-specific failure cases:

```sh
docker exec -w /app speleodb-monorepo-django pytest \
  speleodb/api/v2/tests speleodb/users/tests speleodb/git_proxy \
  --api-contract-report=/tmp/api-contract.json --api-contract-enforce
```

Do not run concurrent database-backed suites against the same test database.
Follow [the GitLab testing rules](ci-gitlab-testing.md): use the existing
canonical fixture pool and retain the audited maximum of nine repository
creations per invocation. Do not substitute production requests or mock every
response to make a contract check pass. A skipped integration case is not
runtime evidence for its branch.

Reports identify the operation, method/path template, actual status and test
case. Version 2 reports contain `observations`, the schema SHA-256 captured when
validation initializes, the pytest invocation, and the effective exit status.
The observer parses the same canonical YAML bytes that it hashes. The separate
export check detects drift between source declarations and that snapshot. The
coverage command rejects reports from failed sessions, including ordinary test
assertion failures, and reports missing their exit status. Violations must be
fixed at the runtime or schema source, then reproduced with relevant cases.
Schema validation alone proves document syntax and references, not endpoint
accuracy. Resolver coverage proves endpoint inclusion, not successful business
behavior. An anonymous 403 does not establish the authenticated 200 shape. Keep
those forms of evidence distinct when reviewing an update.

The observer surrounds application middleware so it validates final responses,
including browser CSRF failures that never reach an auth handler. It selects
operations through the resolver and exported contract, without rewriting an
alias to another mount. Both auth mounts need their own successful workflows or
documented configured-unavailable evidence.

OGC declares `allowEmptyValue` only for query fields where the parser treats an
explicit empty value as omission/default. The observer honors those declarations
before numeric/CSV casting to accommodate openapi-core's casting order; nonempty
values and parameters without that flag retain their normal schema validation.

After a passing audit run, enforce operation coverage and refresh the durable
evidence registry from the observed report:

```sh
docker exec -w /app speleodb-monorepo-django \
  python manage.py verify_api_contract_coverage /tmp/api-contract.json \
  --settings config.settings.test --write
```

When an intentional schema update has made the existing registry stale, run that
audit with only its snapshot guard deselected:

```sh
uv run pytest speleodb/api/v2/tests speleodb/users/tests speleodb/git_proxy \
  --deselect=speleodb/api/v2/tests/test_api_contract.py::test_durable_evidence_matches_current_contract \
  --api-contract-report=/tmp/api-contract.json --api-contract-enforce
uv run python manage.py verify_api_contract_coverage /tmp/api-contract.json \
  --settings config.settings.test --write
uv run pytest \
  speleodb/api/v2/tests/test_api_contract.py::test_durable_evidence_matches_current_contract
```

The first command still executes the actual route, request, response and
business-behavior tests. The final command checks the newly written snapshot.
Normal CI runs the guard with every other test; do not make its exclusion a
permanent pytest setting or accept a report containing other test failures.

Without `--write`, the command validates coverage without modifying the
registry. Its schema hash binds the evidence to the exact canonical YAML, and a
regression test checks that hash and the complete operation set. The command
rejects unknown operations, contract violations, missing observations, and
operations with only admission/error evidence. The registry records actual test
names, statuses, media, request validation flags, and **unobserved declared
statuses**. It is evidence of executed branches, not a claim that every
conceivable input or failure condition has been exercised. Each mounted alias
has its own operation and observations; the independent alias test additionally
proves matching view classes and initialization arguments for all 47 auth
aliases. Git packet-line rejections are recorded even when their HTTP status is
200, but cannot satisfy the successful-operation evidence requirement.

When combining runs made before and after a schema refinement, supply the exact
previous YAML with `--baseline-schema`. The coverage command checks its hash
against the older report, recursively expands local component references for
each operation, and requires current-schema positive evidence for every changed
operation. The registry records report provenance, observed hashes per
operation, and the changed operations that were revalidated. It never implies
that an older response was revalidated against a newer schema. A full run on the
current snapshot needs no baseline argument.

The resolver and generated contract must agree on every supported operation; the
durable registry records the current counts and evidence. Some allauth
operations complete a verified account transition with a 401 flow response:
signup, email verification, password reset, password change and logout for both
clients on both mounts. Their tests verify account/session changes as well as
response bytes. Other allauth operations are configured unavailable: phone
authentication, login by code, email-code resend, and token refresh under
SessionTokenStrategy. Their schemas omit unreachable upstream success responses
and retain real error evidence; the coverage command derives those exceptions
from current settings. Enabling one of those features requires successful
fixtures, rather than a permanent exemption.

The observer validates parameters and bounded JSON/URL-encoded bodies on
successful requests and rendered responses on every observed status. It does not
authenticate test requests itself: existing middleware and real authentication
fixtures do that. Multipart file bodies are exercised by integration scenarios
and real browser XHR; the observer does not preload them into RAM or bypass
upload limits to revalidate their raw bytes. Dynamic experiment rules,
geographic topology, and cross-field constraints still require domain tests. For
successful JSON object requests, the observer also records names of keys absent
from the declared input properties. Review these diagnostics for missing manual
inputs; DRF intentionally ignores some extra fields, so these names do not
automatically fail validation. Values are never recorded. Skipped cases and
listed unobserved statuses must not be reported as verified branches.

Rate limiting is part of the wire contract. The password-change endpoint returns
DRF's 429 `detail` object and required `Retry-After` seconds header. Configured
allauth limiters return a 429 `status` object, optionally with app session
metadata, without `Retry-After`. `AUTH_RATE_LIMIT_ACTIONS` in `schema.py` maps
only handlers that can return that response to their installed allauth actions;
the export checks whether each action is enabled. Disabled features and
unthrottled handlers do not gain a speculative 429. When upgrading allauth,
review its decorators, dispatch guards and rate-limit response paths alongside
that mapping. The limiter bypasses GET unless explicitly configured otherwise;
decorating a handler does not itself prove that its GET requests can be
throttled. The real HTTP regressions consume isolated cache-backed quotas for
every currently enabled mapped operation, both clients and both mounts, and
verify that the corresponding GET handlers continue responding after repeated
calls.

Export history accepts positive page numbers and DRF's `page=last`; invalid or
out-of-range pages return 404. Initial sensor-list validation can return an
`errors` object keyed by invalid row index, for example
`{"errors":{"0":{"name":["This field is required."]}}}`. DRF 3.18's configured
dictionary format omits valid rows; it does not emit the older error array with
empty placeholders. The sensor-create error schema bounds ordinary field errors
and indexed child errors separately from parser errors. Direct contract
assertions verify invalid and mixed lists leave both fleet and sensor row counts
unchanged. Review this shape when upgrading DRF or changing
`LIST_SERIALIZER_ERRORS_AS_DICT`.

OpenAPI objects allow extra keys unless `additionalProperties: false` is
present. Responses using DRF's unchanged model-serializer representation are
closed because it emits only declared fields. Explicit import-summary
dictionaries are also closed. Custom representations, dynamic JSON maps, error
maps and GeoJSON feature properties require their own source/fixture review;
validation of an open object does not establish that every extra key was
declared. Do not add closure globally to silence this limitation or reject
legitimate dynamic data.

## Behavior corrections covered by the contract tests

Profile PUT updates the authenticated user rather than constructing a new user.
Creation paths save server-owned audit fields explicitly. Initial sensor rows
are validated before a fleet is saved, and their creator is recorded. A cylinder
installation requires its project on creation and cannot clear it later because
its model requires that foreign key; omitted creation fields and invalid null
requests return 400. Updates preserve an omitted project. Creation records the
authenticated installer and creator even when the input attempts to override
them. Nullable installation values can still be cleared using all supported
media. A station with no tag returns JSON `null`, rather than an empty body
labeled JSON. Project-team permission lookup reads its team identifier from the
GET query. Spreadsheet tools return validation errors for missing required
inputs instead of leaking KeyError/TypeError as server errors.

`HeadlessAwareHijackUserMiddleware` preserves Django's session-aware lazy user
for only the two mounted allauth **app** route prefixes. The original
django-hijack cookie-user closure prevented allauth from switching to the
X-Session-Token user. Positive app-token flows, missing/invalid tokens, both
mounts, and browser hijack state have real regressions. Browser requests
continue through the normal hijack middleware. The configured allauth schema
also corrects actual 410 session expiry payloads and overlapping
authentication-method alternatives.

The separate `HeadlessPhoneFeatureMiddleware` checks the resolved
phone-management and verification views and current signup settings. When phone
support is absent, GET/HEAD/POST returns 409 before reaching allauth's
unimplemented adapter hooks, including for authenticated users. Both canonical
and alias mounts are covered. The configured export describes this unavailable
operation explicitly; it does not advertise a successful phone-management
response for the disabled feature.

## Automation and synchronized changes

The web `export-api-schema` prek hook regenerates `OpenAPI.yaml` when the
artifact, Python backend/configuration, Python manifest or lock changes. It uses
`pass_filenames: false`, since a schema is generated from the configured
application, not from individual input filenames. Prek reports a modified
artifact for review. No hook installation or staging is part of generation.

Web CI's independent `api-contract` job checks local export drift and compares
the fresh export's SHA-256 with `openapi-source.json` from
`OpenSpeleo/SpeleoDB-TS-API`. Its default counterpart ref is `master`; the
repository variable `API_SCHEMA_REF` can pin a reviewed SDK commit for a
coordinated change. The sparse checkout retrieves only the source record and
does not publish or modify either repository. A missing or invalid record or
changed schema byte fails validation. This job also runs for Dependabot and fork
pull requests with nonsecret export settings; dependency changes cannot bypass
schema freshness or cross-repository equality because a service-backed test job
is unavailable. For a coordinated breaking change, make the counterpart commit
available and configure the reviewed ref before expecting the web CI comparison
to pass; do not weaken the comparison to semantic YAML equality.

The ordinary backend CI pytest invocation enables `--api-contract-enforce` and
writes a report. CI then requires operation coverage with
`verify_api_contract_coverage` and uploads the observations even on failure.
Generated YAML is excluded from style-only yamllint rewriting; exporter
validation, parser checks and byte comparisons remain mandatory.

The monorepo's `openapi-contract-match` prek hook and CI run the parent utility
`utilities/openapi-contract/check.mjs`. That utility hashes the sole checked-out
web schema and compares the digest with the SDK source record; it does not
regenerate, synchronize, stage, or commit files. Web's export check owns
freshness against backend declarations. No second schema is stored in the SDK
repository or its published package.

An exported backend correction can be ahead of the published SDK. The existing
SDK provenance must continue identifying the backend commit that produced that
release. In this state, the cross-repository digest comparison correctly fails;
do not edit the published release's source pin, fabricate a revision, or weaken
the gate. Completing synchronization requires the reviewed backend commit to be
available upstream, followed by SDK regeneration from its real commit and
digest, a new SDK release, and consumer version/lock updates.

For draft generation before that coordinated release, use an isolated SDK
checkout, update that draft's `sha256` to the exported file's digest, and set
its `revision` to `null`. Supply the canonical file explicitly; the SDK never
discovers sibling repositories:

```sh
export SPELEODB_OPENAPI_PATH="/absolute/path/to/web/OpenAPI.yaml"
cd /absolute/path/to/isolated-sdk-checkout
bun run generate
bun run generate:check
bun run typecheck
bun run test
```

The SDK copies the verified input only into its process-owned temporary
generation directory, which is removed afterwards. For standalone regeneration,
publish the reviewed backend commit, record its actual immutable revision in
`openapi-source.json`, and unset `SPELEODB_OPENAPI_PATH`. The default SDK loader
then fetches `OpenAPI.yaml` from that exact backend revision and rejects changed
bytes, redirects and download failures. A null revision is a local maintenance
state that requires the explicit local input for every generation/check command,
not a release-ready source pin. Keep it out of the released SDK checkout. Follow
the SDK maintenance guide for trusted publishing and consumer release order.

Use the SDK's current package scripts and maintenance guide as the authority for
its checks. Review the generated diff, including removals, operation names,
required fields, nullable unions, content types and status unions. Then run web
and mobile checks in their owning repositories. Refresh standalone and
integration locks when package dependencies change. Committing, publishing or
releasing any repository requires its normal explicit authorization; export and
validation do not perform those operations.

## Troubleshooting

- **Different hashes but equivalent YAML:** review the canonical export and
  update the SDK source digest deliberately. Check line endings and formatter
  rules; do not round-trip the file through another YAML tool.
- **Export warnings or duplicate IDs:** identify the source view, imported
  schema or renamed operation. Fix declarations instead of disabling warning
  failures.
- **Nullable object rejected:** retain the required non-null shape and inspect
  the null branch/reference. Do not globally make response fields optional.
- **Generated form code cannot append an object or Blob:** inspect the actual
  request parser/media contract before changing the generator. Opaque JSON may
  need JSON string encoding; binary data requires multipart.
- **Unexpected 401/403:** inspect authentication order and the concrete
  exception. First-party DRF and allauth have different error bodies and flow
  semantics.
- **Wrong download parser:** compare the declared media with the actual header
  and stream bytes. An XLSX filename alone does not determine the response MIME
  type.
- **A new URL is absent from the SDK:** the resolver inventory must fail. Check
  explicit `schema=None`, non-DRF views, conditional URL configuration, and
  imported allauth/OGC sources. Add an explicit source adapter rather than
  excluding the URL.
- **CI counterpart drift:** confirm the intended SDK repository/ref and review
  its source record against the fresh backend export. Updating a package version
  alone cannot synchronize the contract.
