# Upload modals require explicit dismissal

## Correction

Clicking an upload-modal backdrop must not discard the user's selected file or
form state. This applies consistently to GIS Layer uploads and the shared GPX
import used by My GPS Tracks.

## Rule

Upload modals close only through their explicit close/Cancel controls or the
documented Escape-key action. Do not attach backdrop-click dismissal handlers to
upload containers. Add a regression test whenever an upload modal's event wiring
changes.
