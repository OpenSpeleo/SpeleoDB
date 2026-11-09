# Project software and conversion capabilities

Project software identifies the application used to author a survey. It is
separate from an uploaded file's format: choosing a software category does not
install a parser or enable map conversion.

## Choices and ownership

`ProjectType` in `speleodb/common/enums.py` owns the software choices. Software
values are stored in lowercase; project API responses and software selectors use
uppercase labels. API input accepts any letter case. The model choices feed
Django admin forms and filters, project creation/editing, and serializer
validation. Project list badges and dashboard chart colors have their own
presentation mappings.

The serializer's schema extension derives request patterns and response choices
from the enum. Export the canonical web `OpenAPI.yaml`, import its reviewed
bytes into the SDK's local `OpenAPI.yaml` snapshot, update its SHA-256 record,
and regenerate both the TypeScript and Rust SDKs. See
[the contract workflow](api-contract.md). SDK standalone generation uses its
checked-in snapshot independently of backend publication; the monorepo
separately checks local snapshot agreement.

## Capabilities

| Project software                 | Existing file upload/storage | Survey-to-GeoJSON conversion                     |
| -------------------------------- | ---------------------------- | ------------------------------------------------ |
| Ariane                           | Yes                          | Supported for recognized survey sources          |
| Compass                          | Yes                          | Supported for complete recognized survey bundles |
| Stalagmight                      | Yes                          | Supported for recognized native SQLite surveys   |
| StickMaps, Therion, Walls, Other | Yes                          | Unsupported                                      |

## File processing

Ariane, Compass, and Stalagmight use the same upload, revision history, and
format-specific download workflow. AUTO uploads select the processor by file
extension. Ariane TML validates ZIP content; Stalagmight validates SQLite
content before storing the original file bytes. See the
[shared file API](project-edition-and-upload.md#file-api) for routes.

## Conversion behavior

Ariane, Compass, and Stalagmight support survey conversion. Stalagmight uses
`StalagMightInterface.from_file()` from `openspeleo_lib.interfaces`, followed by
the common `survey_to_geojson()` exporter. Explicit STALAGMIGHT and AUTO uploads
request background generation when the project software matches the source.
SQLite integrity validation and byte-for-byte storage happen before scheduling;
a supported survey schema is not required to save a source. Semantic errors fail
optional generation without rejecting the upload or removing the last usable
map. Uploads without eligible survey sources report
`geojson_status: not_requested`; the independent `exclude_geojson` flag produces
`skipped`. Uploading a file does not change the project's software category.

Existing map artifacts remain readable after a software change. See
[background generation](project-geojson-background.md) and
[historical rebuilds](project-geojson-command.md) for the conversion workflows.

## Verification

Regression coverage exercises case-insensitive API writes and canonical reads,
invalid choices, admin forms/filtering, selected dropdown options,
desktop/mobile badges, dashboard counts/colors, and project settings without a
map-status panel.

File-processing tests cover content validation, explicit/AUTO selection,
permissions, edition locks, downloads, revision history, unchanged uploads,
rollback, and conversion eligibility.

Run web tests in the existing application container. Verify schema freshness,
frontend tests/types, and Python lint/types. No schema or SDK change is needed
to enable conversion for an existing software choice. Existing Ariane/Compass
conversion tests remain regression controls.
