# Project software and conversion capabilities

Project software identifies the application used to author a survey. It is
separate from an uploaded file's format: choosing a software category does not
install a parser or enable map conversion.

## Choices and ownership

`ProjectType` in `speleodb/common/enums.py` owns the software choices.
Stalagmight is stored as `stalagmight`; project API responses and existing
software selectors use `STALAGMIGHT`. API input accepts any letter case. The
model choices feed Django admin forms and filters, project creation/editing, and
serializer validation. Project list badges and dashboard chart colors have their
own presentation mappings.

The serializer's schema extension derives request patterns and response choices
from the enum. Export the canonical web `OpenAPI.yaml`, import its reviewed
bytes into the SDK's local `OpenAPI.yaml` snapshot, update its SHA-256 record,
and regenerate `@speleodb/api`. See [the contract workflow](api-contract.md).
SDK standalone generation uses its checked-in snapshot independently of backend
publication; the monorepo separately checks local snapshot agreement.

## Capabilities

| Project software                              | Existing file upload/storage | Survey-to-GeoJSON conversion                     |
| --------------------------------------------- | ---------------------------- | ------------------------------------------------ |
| Ariane                                        | Yes                          | Supported for recognized survey sources          |
| Compass                                       | Yes                          | Supported for complete recognized survey bundles |
| Stalagmight, StickMaps, Therion, Walls, Other | Yes                          | Unsupported                                      |

Stalagmight uses the existing generic upload and revision/download workflows.
There is no native Stalagmight file processor or format-specific download link.
`FileFormat` continues to describe the actual files handled by processors.

## Existing conversion behavior

Stalagmight follows the same unsupported-software behavior as StickMaps,
Therion, Walls, and Other. Only Ariane and Compass have survey exporters.
Generic uploads do not request GeoJSON generation for unsupported software;
`geojson_status` is `not_requested` unless the independent operator exclusion
flag is enabled. Selecting Stalagmight does not set `exclude_geojson`.

Existing map artifacts remain readable after a software change. This software
choice adds no conversion policy, scheduling changes, or map-read restrictions.
See [background generation](project-geojson-background.md) and
[historical rebuilds](project-geojson-command.md) for the existing workflows.

## Verification

Regression coverage exercises case-insensitive API writes and canonical reads,
invalid choices, admin forms/filtering, selected dropdown options,
desktop/mobile badges, dashboard counts/colors, and the unsupported conversion
notice.

Run web tests in the existing application container. Verify schema
freshness/hash equality, SDK regeneration and build, frontend tests/types/build,
and Python lint/types. Existing Ariane/Compass conversion tests remain
regression controls.
