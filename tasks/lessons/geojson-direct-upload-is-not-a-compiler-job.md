# GeoJSON direct upload is not a compiler job

## Correction

When a browser map already accepts GeoJSON, do not route an uploaded GeoJSON
file through the KML/KMZ conversion architecture. Upload progress completing
does not mean a later POST began: it means the request body of the already
active POST finished transferring while the browser waits for the response.

## Rule

Keep native GeoJSON ingestion to the unavoidable work: select it from the
declared upload format and write the source bytes once. Serve that exact object
to Mapbox through a permission-checked signed URL. Do not parse, normalize,
hash, recount, reserialize, or duplicate it into display objects unless a
product requirement explicitly needs conversion.

Use conversion only for source formats such as KML/KMZ
that Mapbox cannot consume directly.

Do not add endpoint throttling as an unsolicited review hardening measure.
Resource bounds and rate policy are different product decisions; a failed
upload must not unexpectedly lock a user out of the next attempt.
