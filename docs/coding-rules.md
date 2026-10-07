# Coding Rules

Hard rules for all code in this repository. Violations must be fixed before
merging.

---

## JavaScript / Frontend

### All constants belong in `config.js`

**Every tuneable constant** in the map viewer must be defined in the `DEFAULTS`
object exported from `config.js`. No magic numbers, thresholds, durations, zoom
levels, colors, sizes, or configuration values anywhere else.

```javascript
// BAD — hardcoded constant in a random module
const DRAG_THRESHOLD = 10;
const LIMITED_MAX_ZOOM = 13;
map.fitBounds(allBounds, { padding: 50, maxZoom: 16 });
setTimeout(() => overlay.remove(), 500);

// GOOD — import from config.js
import { DEFAULTS } from "../config.js";
// ...then use DEFAULTS.DRAG.THRESHOLD_PX, DEFAULTS.MAP.LIMITED_MAX_ZOOM, etc.
```

The `DEFAULTS` object is organized by category:

| Category                | Examples                                                                                                                                                    |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DEFAULTS.MAP`          | style URL, center, zoom levels, fit bounds padding                                                                                                          |
| `DEFAULTS.ZOOM_LEVELS`  | min zoom per layer type                                                                                                                                     |
| `DEFAULTS.SNAP`         | magnetic snap radius                                                                                                                                        |
| `DEFAULTS.DRAG`         | drag threshold, query padding                                                                                                                               |
| `DEFAULTS.UI`           | mobile breakpoint, notification duration, truncation lengths, `COUNTRY_GROUP_TRANSITION_MS`                                                                 |
| `DEFAULTS.UPLOAD`       | max file size                                                                                                                                               |
| `DEFAULTS.COLORS`       | `DEFAULT_STATION`, `FALLBACK` (`#94a3b8` — used when model color is not yet loaded), `DEPTH_NONE`/`DEPTH_SHALLOW`/`DEPTH_MID`/`DEPTH_DEEP` (depth gradient) |
| `DEFAULTS.STORAGE_KEYS` | localStorage key names: `COUNTRY_COLLAPSED`, `COUNTRY_VISIBILITY`, `PROJECTS_COUNTRY_COLLAPSED`, plus project/network visibility keys                       |

When adding a new feature that needs a tuneable value, add it to `DEFAULTS`
first, then import it where needed.

### No unescaped user data in HTML sinks

**Every** `innerHTML` assignment, jQuery `.html()` call, or `insertAdjacentHTML`
that interpolates user- or API-supplied data **must** escape that data first.
This applies to every application module, including shared form helpers.
Templates provide inert JSON context; executable inline application scripts are
not part of the asset contract.

```javascript
// BAD — user data injected raw into HTML
el.innerHTML = `<h3>${station.name}</h3>`;
$("#error").html(errorMsg);

// GOOD — ES module: use Utils.safeHtml / Utils.escapeHtml
el.innerHTML = Utils.safeHtml`<h3>${station.name}</h3>`;
html += `<td>${Utils.escapeHtml(value)}</td>`;

// GOOD — form module: import escapeHtml or use .text()
$("#error").text(errorMsg);
tableBody.html(`<td>${escapeHtml(tag.name)}</td>`);

// GOOD — safe alternative: textContent (never parses HTML)
el.textContent = station.name;
```

**Attribute contexts** (e.g. `value="..."`, `data-*="..."`) require quote
escaping. `Utils.escapeHtml` escapes `"` and `'` in addition to `<`, `>`, `&`.

**`Utils.raw()`** marks content as pre-trusted and bypasses escaping. Never wrap
strings that contain unescaped user data in `Utils.raw()`.

**CSS color values** in `style` attributes must be validated with
`Utils.isValidCssColor()` or `Utils.safeCssColor()` before interpolation.

**URL attributes** (`href`, `src`) with API-supplied values must be validated
with `Utils.sanitizeUrl()` to block `javascript:` and other dangerous schemes.

**Inline application event handlers** (`onclick="..."`) are prohibited. Use
inert `data-*` actions with delegated listeners or `addEventListener` in
modules.

**Do not** define local `escapeHtml` / `safeCssColor` copies in templates or
standalone scripts. Form/route modules import the ES exports from
`xss-helpers.js`; map modules use `Utils` from `utils.js`. URL scheme validation
is not quote escaping: insert `sanitizeUrl()` results through `safeHtml`,
`escapeHtml`, or a DOM property rather than raw quoted HTML interpolation.

See `docs/xss-protection.md` for the full rationale and patterns.

### Stable `data-*` hooks

Some `data-*` attributes are queried by runtime JS, tests, or both (e.g.
`data-experiment-readonly-notice`, `data-experiment-action`,
`data-modal-close`). Treat them as stable DOM hooks, not styling hooks.

- **Runtime JS and tests** may query them via `querySelector`,
  `querySelectorAll`, or `closest`.
- **CSS** must NOT take a dependency on them. Style with classes instead.
- **Removing or renaming** a `data-*` test hook is a coordinated change: every
  caller (runtime code and every spec that queries it) must be updated in the
  same commit. Treat it like a public API rename.

When introducing a new test-stable attribute, add a JSDoc-style comment above
the rendering function that documents the contract. See
`renderReadOnlyExperimentNotice` in `experiments.js` for the pattern.

---

## Python / Backend

### Application timestamps

- Use `from django.utils import timezone` and call `timezone.now()` for current
  application timestamps, including generated API timestamps and epoch seconds
  (`timezone.now().timestamp()`). Convert to UTC explicitly when a wire format
  ends in `Z`; use `timezone.localtime()` / `timezone.localdate()` for local
  presentation and calendar dates.
- Capture one `now` for related fields in a state transition. Export attempt
  creation and its initial dispatch eligibility must use the same instant.
- Django model `default=timezone.now` is a valid fallback, but retains the
  callable selected when the model is imported. Service transitions that must
  follow a replaceable clock should pass explicit timestamps. Test factories
  should resolve `timezone.now()` inside their lazy callback rather than retain
  the original callable.
- Test clock-sensitive transitions with a controlled Django clock, including
  just before and exactly at deadlines. Keep monotonic/performance clocks for
  elapsed durations and process timeouts; they are not calendar timestamps.

### Import & Module-Level Code

- **All imports must be at the top of the file.** Never use inline/local imports
  inside functions, methods, or `setUp`. This violates ruff PLC0415. If you need
  a symbol, import it at the top with all other imports.

```python
# BAD — inline import inside a method
def test_something(self) -> None:
    from speleodb.common.enums import ProjectType  # PLC0415!

    ...


# GOOD — import at the top of the file
from speleodb.common.enums import ProjectType


def test_something(self) -> None: ...
```

- **Never place executable statements (assignments, function calls) between
  import groups.** `logger = logging.getLogger(__name__)` and similar
  module-level assignments go **after all imports** (including
  `if TYPE_CHECKING` blocks), never in the middle. Violating this causes ruff
  E402 for every import that follows.
- Import order enforced by ruff/isort: `__future__` -> stdlib -> third-party ->
  local -> `TYPE_CHECKING`. No code between these groups.

### Django ORM

- **Never materialize a queryset to grab one element.** Use `.first()` /
  `.last()` / `.get()`, not `list(qs)[0]`.
- **Never filter in Python when the ORM can do it.** Use
  `.filter(field=value).first()`, not
  `next(x for x in qs.all() if x.field == value)`.
- **Use `.count()` not `len(list(qs))`, `.exists()` not `bool(list(qs))`.**
- Always add `select_related()` / `prefetch_related()` when accessing FK fields
  in serializers or loops to avoid N+1 queries.

Do not replace separate indexed counts with a `Case`/`When` aggregate merely to
reduce query count. Compare representative query plans and timings with
`EXPLAIN ANALYZE`; conditional aggregation may trade fewer round trips for a
larger scan. Account for intentional prefetch caches when assessing total query
cost rather than treating every ORM call as free.

### URL transport in integration tests

Generated URLs are still untrusted transport inputs. Parse them, require a
hostname, and allow only `http`/`https` before connecting with a finite timeout.
The local-storage tests use `HTTPConnection`/`HTTPSConnection`; do not replace
this boundary with unrestricted `urllib.request.urlopen`. Cover unsupported
schemes and missing hosts. Ruff `noqa` comments do not suppress or resolve
Bandit findings; run the actual security hook for security-sensitive transport
edits.

### Typed framework and test boundaries

Run mypy after model ownership/field changes and after the final fixture edit.
Fix stale queryset fields and attributes instead of hiding drift with broad
ignores. Narrow nullable values before ORM use, framework response types before
reading type-specific attributes, and third-party optional process handles
before transferring ownership. Keep annotations at genuinely untyped library
boundaries narrow and explain upstream stub gaps.

Include new untracked files in direct lint/type checks: Git-based hook
inventories may omit them. Use `PropertyMock` for a read-only property when a
unit test needs one, and keep setup outside `pytest.raises` so only the intended
failing operation is covered.

Annotate a fixture that yields without a value as `Generator[None, None, None]`,
not `None`. Give heterogeneous nested fixture mappings an explicit mapping type
or `TypedDict` before indexing their values. Runtime pytest success does not
validate these annotations; rerun the normal mypy check after the final fixture
edit.

For fixture-heavy test signatures, a line-scoped complexity `noqa` is preferable
to distorting the fixture contract. Dummy test credentials may need a narrow
S106 suppression with a test-only explanation. Do not weaken runtime secret
requirements or substitute Ruff suppression for Bandit verification.

### File responses in the API schema

Schema-exposed `GenericAPIView` downloads need a concrete `serializer_class` for
lookup/introspection even when they return files. Annotate the method with
`extend_schema` and the real binary media type, such as
`{(200, "application/gpx+xml"): OpenApiTypes.BINARY}`. Run
`speleodb/users/tests/test_swagger.py::test_api_schema_no_warnings` in the
application container for schema-facing changes.

### Permission endpoint ownership

Use the established concrete, typed model-specific views and serializers. Reuse
cross-entity validation helpers while keeping authorization and transaction
scope visible at each endpoint. A subset-only dynamically configured permission
base is not a reason to migrate unrelated entities; shared infrastructure needs
a coherent contract across its actual consumers.

### Transaction failure recovery

Catch recoverable `IntegrityError` outside a nested `transaction.atomic()` block
so its savepoint rolls back before subsequent queries or a controlled 400
response. Catching inside the broken transaction is not sufficient.

### OGC URL construction

OGC child-link builders use `request.path`, never `request.get_full_path()`:
query strings must not become part of child paths. The shared `absolute_url()`
in `speleodb/gis/ogc_helpers.py` owns absolute URL construction. Keep filters in
their intended query parameters and exercise discovery with query strings.

### Migration state compatibility

When replacing a constraint, read every intervening migration and use the name
present at the immediate dependency state. Test forward migration from that
state and restore the latest graph afterward; an original constraint name may
have been renamed before the new migration.

A new non-null field on a central model can break migration tests that insert
through an older historical model while another app's table remains current.
Where such inserts must work, supply a database `db_default` as well as the
normal Python `default`, and include it in the migration. For example,
`User.has_api_doc_access` uses both defaults as `False`. Verify cross-app
rollback/reapply rather than relying only on current-model saves.

### Permission mutation and deletion contracts

Permission endpoints reject missing body fields with `MissingFieldError` (400),
not resource-not-found 404. Validate prohibited levels before database writes;
team project permissions exclude ADMIN. Shared self-target validation owns that
guard instead of unreachable duplicate view branches. PUT updates active grants;
POST owns reactivation and clears deactivation metadata. Repeated revocation
returns 404 once no active grant remains.

Top-level collaborative entities use their established soft-delete/deactivation
flows to retain membership and audit history. Do not replace these with a hard
delete merely to simplify an endpoint. Team deletion deactivates memberships and
project permissions while retaining the team row. Child-record hard deletion is
a separate domain contract. Any intentional cascade deletion needs review of
signals and `on_commit` callbacks: capture needed scalar identifiers while rows
exist, and exercise commit callbacks in the regression instead of relying on a
TestCase rollback that never executes them.

Permission tests cover the actual level/access-type matrix, self-target guards
on every supported mutation method, inactive grants, reactivation audit fields,
and repeated DELETE. List tests assert exact count/types and tenant isolation
with unrelated and inactive rows. Do not hedge serializer types with
`x or str(x)` assertions. Factories using `django_get_or_create` on generated
emails need explicitly unique values when distinct users are required.

### Production settings under DEBUG

When a production-derived value must be checked under DEBUG, compute it under an
explicit production-contract name outside the DEBUG branch, then assign the
runtime setting only in its normal production branch. For example,
`PRODUCTION_CORS_ALLOWED_ORIGINS` remains inspectable in either mode without
changing debug CORS behavior or weakening the test.

## Verification command scope

The root prek configuration excludes `bin/` from file-based hooks. Historical
maintenance tools such as `bin/squash_dependencies.py` therefore are not covered
by a passing Ruff hook; an unrestricted `ruff check .` has a different scope.
Report the actual command and checked scope instead of treating hook success as
proof that every repository script is lint-clean. This exclusion does not waive
coding rules for scripts being changed. The full-project mypy hook has its own
configured discovery and does not receive prek's selected filenames; see
[mypy scope and cache ownership](mypy-cache.md).
