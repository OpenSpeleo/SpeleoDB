# SpeleoDB documentation

Feature guides describe what SpeleoDB does and how its features behave.
Architecture references explain the implementation and its contracts. Operations
and development guides cover running and maintaining the application. Agent
guidance is explicitly labeled **Agent Documentation & Practices**; feature
guides are not task plans or implementation journals.

## Accounts and dashboard

- [Dashboard](dashboard.md)
- [Account names and Git authorship](user-identity.md)
- [Application token copying](profile-token-copy.md)
- [API documentation access](api-docs-access.md)
- [Account exports](account-export-backup.md) and
  [export page, API, and administration](export-interfaces.md)
- [Public supporters directory and giving](supporters.md)
- [Donation campaigns](donation-campaign.md) and
  [campaign backend](donation-campaign-backend.md)
- [Donation thank-you emails and acknowledgment letters](donation-acknowledgments.md)

## Survey projects and data

- [Project listing](project-listing.md)
- [Project editing and revision submission](project-edition-and-upload.md)
- [Survey software and conversion capabilities](project-formats.md)
- [Survey loop closure](survey-loop-closure.md)
- [Project and GPS track colors](project-colors.md)
- [Exploration leads from survey comments](exploration-lead-import.md)
- [GPS tracks](gps-tracks.md)
- [Landmark collections](landmark-collections.md)
- [Experiment field names](experiment-field-names.md)
- [Experiment record editing](experiment-record-editing.md)
- [Compass Sidecar release links](compass-sidecar-release-link.md)

## Maps and geographic data

- [Map viewer features](map-viewer/features.md)
- [Map viewer feature contracts](map-viewer/design-requirements.md)
- [Permissions and access](map-viewer/permissions-and-access.md)
- [Private map display settings](map-viewer/settings.md)
- [Importing places and overlays](map-viewer/import.md)
- [Distance ruler](map-viewer/measurement.md)
- [Survey section coloring](map-viewer/shot-coloring.md)
- [Depth coloring](map-viewer/map_viewer_depth_coloring.md)
- [Depth domain updates](map-viewer/depth-domain-reactivity.md)
- [GIS layers](gis-layers.md)
- [GIS geometry editing](gis-geometries.md)
- [Public GIS view geographic bounds](gis-view-geographic-bound.md)

## APIs and architecture

- [API contract ownership](api-contract.md)
- [Generated TypeScript API client](typescript-api-client.md)
- [Map viewer API reference](map-viewer/api-reference.md)
- [GIS geometry read API](gis-geometry-read-api.md)
- [OGC URLs and geometry contracts](map-viewer/ogc-url-and-geometry-contract.md)
- [Map viewer architecture](map-viewer/architecture.md)
- [Map viewer data flow](map-viewer/data-flow.md)
- [Responsive viewer updates](map-viewer/async-updates.md)
- [Shared map packages](map-viewer/shared-packages.md)
- [Survey GeoJSON artifacts](project-geojson-artifacts.md)
- [Background survey map generation](project-geojson-background.md)
- [Git Smart HTTP proxy](git-proxy.md)
- [GitLab reliability](gitlab-reliability.md)
- [Bounded operational retries](bounded-retries.md)
- [Export storage and signed downloads](export-storage-policy.md)
- [API error handling](upload-error-handling.md)
- [HTML escaping and XSS protection](xss-protection.md)

## Administration and operations

- [Administrator operations](admin-operations.md)
- [Administrator audit history](admin-audit-logging.md)
- [Background jobs and task history](background-jobs-operations.md)
- [Project GeoJSON command](project-geojson-command.md)
- [Email delivery and Mailpit](email-delivery.md)
- [Production Railway configuration](railway-production.md)
- [Git backup and Gogs operations](git-backup-operations.md)
- [Persistent GitLab for CI](gitlab-test-railway.md)

See also the top-level [Railway guide](../RAILWAY.md) and
[GitLab connection settings](../OPTIONS.md).

## Frontend implementation

- [TypeScript architecture](typescript-architecture.md)
- [Vite assets](vite-assets.md)
- [Bun tooling](bun-tooling.md)
- [Tailwind CSS architecture](tailwind-v4.md)
- [Shared forms](frontend-forms.md)
- [Dates and time zones](frontend-dates.md)
- [Logo assets](logo-assets.md)
- [Navigation icon styling](navigation-icon-styling.md)

## Development and testing

- [Local services and object storage](local-object-storage.md)
- [Local debugging](local-debugging.md)
- [Monorepo native dependencies](monorepo-native-dependencies.md)
- [Dependency updates](dependency-updates.md)
- [Real GitLab integration tests](ci-gitlab-testing.md)
- [Git retry testing](git-retry-testing.md)
- [Pytest collection](pytest-collection.md)
- [Mypy cache ownership](mypy-cache.md)
- [Django template linting](template-linting.md)
- [Map viewer testing](map-viewer/testing-and-quality.md)
- [Browser workflows](../tests/browser/README.md)

## Agent Documentation & Practices

- [Repository agent instructions](../AGENTS.md)
- [Feature implementation and review practices](agent-practices.md)
- [Coding rules for agents and contributors](coding-rules.md)
- [CodeRabbit review guidance](coderabbit.md)
- [Automated XSS review instructions](../.github/instructions/xss-protection.instructions.md)

Agent-specific instructions live in clearly labeled practices guides. Temporary
plans, review notes, and progress records belong outside the checkout, as
described in the repository instructions.
