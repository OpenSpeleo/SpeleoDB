# Map Viewer: Permissions and Access Model

Agent-focused reference for permission logic used by map viewer modules.

## Design Intent

Permission decisions should be consistent across all map viewer features.

In particular:

- no feature should independently redefine read/write/delete logic
- station, exploration lead, cylinder, and UI action gating should share the
  same central permission APIs
- unknown/missing permissions fail closed

## Source of Truth

All access checks should route through:

- `frontend_private/static/private/js/map_viewer/config.js`

Use these methods preferentially:

- `Config.hasProjectAccess(projectId, action)`
- `Config.hasNetworkAccess(networkId, action)`
- `Config.hasScopedAccess(scopeType, scopeId, action)`
- `Config.getStationAccess(station)`

Backward-compatible wrappers are still present, but should map directly to
central APIs:

- `hasProjectReadAccess`, `hasProjectWriteAccess`, `hasProjectAdminAccess`
- `hasNetworkReadAccess`, `hasNetworkWriteAccess`, `hasNetworkAdminAccess`

## Permission Semantics

### Project permissions

Ranked model:

- `UNKNOWN` = 0
- `WEB_VIEWER` = 1
- `READ_ONLY` = 2
- `READ_AND_WRITE` = 3
- `ADMIN` = 4

Action thresholds:

- read: rank >= `READ_ONLY`
- write: rank >= `READ_AND_WRITE`
- delete: rank >= `ADMIN`

### Network permissions

Level model:

- read: level >= 1
- write: level >= 2
- delete: level >= 3

If numeric `permission_level` is present, it takes precedence over label fallback.

## Scope Routing Rules

`Config.getStationScope(station)` determines project vs network scope:

- if `station.network` exists, station is treated as network-scoped
- if `station.station_type === 'surface'`, station is network-scoped
- otherwise project-scoped

`Config.getStationAccess(station)` returns:

- `scopeType`
- `scopeId`
- `read/write/delete`

This should be used by station-facing UI/actions to avoid branching drift.

## Engineering Scope

Permission consistency should be maintained across modules that gate actions,
including:

- `stations/*`
- `surface_stations/*`
- `exploration_leads/*`
- map interactions and context-menu action generation

## Testing Coverage

Comprehensive permission tests live in:

- `frontend_private/static/private/js/map_viewer/config.permissions.test.js`

Coverage includes:

- normalization helpers
- project/network matrix behavior
- scope routing
- station access resolution
- invalid action fallback
- fail-closed behavior on internal errors

## Regression Checklist

When touching permission code:

1. Ensure all new checks use central Config APIs.
2. Verify no special-case feature bypasses write/delete rules.
3. Run:
   - `npm run lint:js`
   - `npm run test:js`
4. Confirm UI and action availability is consistent for:
   - `WEB_VIEWER`
   - `READ_ONLY`
   - `READ_AND_WRITE`
   - `ADMIN`

