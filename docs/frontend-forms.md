# Shared frontend forms

Shared form modules own validation, modal lifecycle, pending controls, escaped
error presentation, and navigation after success. Route controllers own the
resource-specific generated API operation. This separation keeps one HTTP
contract in `@speleodb/api` while allowing the same form UI to serve projects,
teams, fleets, layers, tracks, and other entities.

See [Generated TypeScript API client](typescript-api-client.md) for
session/CSRF, request encoding, status handling, file transfers, upgrades, and
verification. The browser adapter in `frontend_common/api/client.ts` provides
`webApiOptions`, `apiData`, and `ApiRequestError`. Shared form helpers receive
promise-returning callbacks, never URLs, HTTP methods, or jQuery AJAX options.

## Ownership and initialization

`frontend_common/entries.json` and the Vite bootstrap resolve inert route
controller identifiers. Django templates render JSON context containing UI
settings and resource identity. Controllers import shared helpers and build
callbacks from concrete generated SDK operations. An entity settings controller
can use `frontend_common/api/entity-forms.ts`, whose finite resource cases build
proper generated request bodies. Permission controllers use
`frontend_common/api/permissions.ts` for the same purpose.

Django owns the authorization rules and server-rendered access controls. Client
validation improves feedback and does not authorize a request. Avoid duplicating
permission matrices in templates or form helpers. A disabled UI is not a
substitute for endpoint permission tests.

Shared contracts live in `ts-types/domain/forms/`; controller context contracts
live in `ts-types/controllers/`. API DTOs come from `@speleodb/api`. Form input
models describe HTML values and local UI state, which can legitimately differ
from server DTOs. Convert them at the controller boundary with typed field and
enum validation.

## Common helpers

| Helper                     | Responsibility                                                                | Controller-supplied API callbacks                 |
| -------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------- |
| `entity_crud_form.ts`      | Collect values, validate, disable submission, show success/error and redirect | `submit`; optional `prepare` converts form values |
| `danger_zone.ts`           | Confirm and perform entity removal                                            | `remove`                                          |
| `mutex_lock.ts`            | Acquire/release a project lock with pending-state protection                  | `acquire`, `release`                              |
| `fleet_settings_form.ts`   | Save fleet metadata and initial sensor rows                                   | `save`                                            |
| `fleet_entity_crud.ts`     | Add/edit/delete fleet children with field collectors                          | `create`, `update`, `remove`                      |
| `tagged_entity_list.ts`    | Refresh and edit a typed list                                                 | `list`, `create`, `update`, `remove`              |
| `permission_modal.ts`      | Add/edit/remove user access or team membership                                | `operations.create`, `.update`, `.remove`         |
| `team_permission_modal.ts` | Add/edit/remove project access for a selected team                            | `operations.create`, `.update`, `.remove`         |
| `gis_view_form.ts`         | Project picker, optional pinned commits, create/edit GIS view                 | `projects`, `commits`, `save`                     |
| `api_errors.ts`            | Safely present adapter errors and serializer validation fields                | No transport                                      |

Forms release controls on rejected promises as well as synchronous request-body
validation failures. Success callbacks may navigate, refresh an owning list, or
schedule the existing reload behavior. Keep that lifecycle at the UI boundary;
the SDK does not retry, reload, open a modal, or interpret permissions.

The callbacks should return the generated operation's result through `apiData`
when ordinary documented 2xx behavior applies. Exceptional statuses are handled
explicitly by the owning controller. The shared form helper must not make an
undocumented response successful to keep an old test fixture working.

`api_errors.ts` reads the adapter error's untrusted `data`, `status`, and
`message`. Serializer field names and values are escaped before HTML rendering;
simple messages use `.text()`. A fallback is shown for transport failures and
unrecognized error bodies. Never insert raw response text as HTML.

## Permissions and autocomplete

User permission forms retain their distinction between creating a grant and
updating one. Editing locks the principal; deleting identifies the exact user or
team. Team membership uses its generated role enum, while project and entity
permissions use the appropriate generated level enum. The controller's callback
converts form values and calls the correct concrete operation; helpers do not
build paths from the resource name.

`user_autocomplete.ts` uses the generated autocomplete operation, a debounce,
and an `AbortController`. Superseding input cancels obsolete work, and stale
responses must not overwrite newer suggestions. Results are the documented bare
array. Suggestions render names and emails as text, preserve keyboard selection,
and hide for a short query, an invalid response, or a failed request.

## Authentication forms

The public `auth_form.ts` helper retains pending controls, validation, success
messaging, and callbacks. Its controller chooses a generated allauth browser
operation for login, signup, password reset request, or reset completion.
Request preparation remains a form concern; CSRF is resolved by the common
browser adapter at request time.

Signup's documented `401` outcome is an intentional next authentication step and
is handled by its controller. Other errors remain errors. A throwing custom
error presenter must not leave the form pending or cause an unhandled promise
rejection. Allauth error structures are interpreted only by the auth UI; they
are not generalized into other endpoint success rules.

## File and survey tools

`tool_file_upload.ts` provides the shared DMP file picker/drop zone and
extension validation. `survey_table_tool.ts` owns editable table rows, cell
validation, clipboard parsing, final-row constraints, and table controls. Each
tool controller creates its own generated request:

- DMP to JSON and DMP Doctor use typed multipart bodies.
- XLS to DMP and XLS to Compass use typed JSON bodies.
- Binary conversion responses remain binary at the SDK boundary. DMP to JSON and
  XLS to Compass decode the returned file to text for their code preview; binary
  download tools preserve the returned bytes.

Code previews escape text before highlighting. Download object URLs are revoked
and temporary anchors removed. The external Nominatim search remains a separate
non-API request with no SpeleoDB credentials. Conversion requests use generated
operations; an external geocoder does not justify another first-party transport.

The shared upload progress component accepts a generated-operation callback and
returns an `AbortController`. GIS layer and map import widgets retain their
transfer/processing distinction, cancellation behavior, blocked dismissal while
publication is pending, and explicit uncertain-result handling. After successful
publication, a failed map refresh is reported separately so users do not upload
the same content again. See [Map file import](map-viewer/import.md).

## Verification and extension

Tests run inside the existing web container as described by `AGENTS.md`.
Frontend tests use real jQuery, actual DOM controls, generated operations, and a
local HTTP server. The helper in `frontend_common/test/api-server.ts` configures
JSDOM through its supported API and serves real HTTP responses. Multipart fetch
tests use a coherent set of real native body constructors; XHR tests use JSDOM's
real multipart implementation. This avoids fabricating SDK response objects or
replacing a transport with jQuery callback mocks.

Tests cover correct paths, methods, query/body encoding, current CSRF headers,
validation text escaping, abort/stale-result behavior, special statuses, binary
responses, and UI settlement. MapLibre renderer replacement is limited to tests
where JSDOM cannot provide its required WebGL context. Live Django upload tests
also verify stored artifacts and authenticated CSRF behavior.

When adding a form, first confirm the endpoint's audited schema and generated
operation. Reuse the applicable form primitive, add a typed controller context,
build the callback, and cover its DOM-to-HTTP behavior. Run `bun run typecheck`,
`bun run lint:frontend`, `bun run audit:api`, `bun run test:frontend`, and the
production build. The AST API audit prevents first-party raw transport calls
from returning under aliases or new endpoint strings.
