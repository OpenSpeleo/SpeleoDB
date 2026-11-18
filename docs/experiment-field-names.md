# Experiment Field Names

## Overview

Experiments allow users to define custom data-collection fields (e.g. "pH
Level", "Nitrate No3-N (mg/L-N)") for scientific measurements at cave stations.
Field names are user-supplied free-text labels.

## Design Intent

Field names preserve the user's letter case; sanitization still applies as
described below. This preserves scientific notation, chemical formulas, and unit
abbreviations that would be broken by automatic titlecasing (e.g. `mg/L-N` must
not become `Mg/L-N`).

Existing stored labels retain their saved case, including labels titlecased by
older application behavior. Case-preserving validation does not reconstruct the
original spelling or automatically rewrite those labels.

## Sanitization

Field names are sanitized via `sanitize_field_name()` (defined in
`speleodb/utils/sanitize.py`). This function:

1. Strips all HTML tags (defense-in-depth against stored XSS).
2. Unescapes HTML entities.
3. Applies NFC normalization (compose, never strip accents).
4. Removes control / format characters.
5. Collapses whitespace and strips edges.

Accented characters (`é`, `ñ`, `ü`, etc.) are **preserved**. This differs from
`sanitize_text()`, which preserves ordinary accents but caps stacked combining
marks. Scientific field labels retain their existing NFC-only policy.

### Where sanitization is applied

- **API path (serializer):** The Pydantic `ExperimentFieldDefinition` model has
  a `sanitize_name` field validator that applies `sanitize_field_name()`. The
  serializer persists the sanitized result via `field_def.model_dump()`.

- **Direct ORM path:** The model's `clean()` validates structure via Pydantic
  (which runs `sanitize_field_name` internally) but does **not** persist the
  sanitized result back to `experiment_fields`. This is by design -- direct ORM
  usage (tests, factories) is trusted to supply clean data.

## Uniqueness

Field names must be unique within an experiment. Uniqueness checks are
**case-insensitive** (via `.lower()`) at both the model and serializer layers.
Two fields named `"pH Level"` and `"ph level"` are considered duplicates.

## Mandatory Fields

Every experiment has two mandatory fields identified by fixed UUIDs:

- `Measurement Date`
- `Submitter Email`

Their canonical identities are defined by `MandatoryFieldUuid` in
`speleodb/gis/models/experiment.py`.

During experiment creation (when fields have no UUID), mandatory fields are
matched by **exact string equality** against their canonical names. The frontend
always sends these exact strings from template data. API clients must use the
canonical names exactly.

## Display-Layer Escaping

Field names are escaped at the display layer regardless of storage sanitization:

- Django templates use default autoescaping (`{{ field_data.name }}`).
- JS uses `escapeHtml()` before any HTML insertion.
- No `|safe` filter or `{% autoescape off %}` is used on field names.

## Browser field editor

`frontend_private/static/private/ts/experiment-fields.ts` owns the dynamic field
editor and its mutable `ExperimentFields` facade. Its jQuery reference is
captured during import and its generated field counter survives repeated
initialization. Validation compares trimmed, case-insensitive names without
rewriting input values; multiple-choice labels are escaped before rendering.
Tests cover duplicate-name styling, incomplete fields, and delegated tag
editing.

Django admin presents experiment field definitions as read-only JSON through
`ExperimentAdmin.raw_experiment_fields_json` in
`speleodb/gis/admin/experiment.py`. Schema changes use the experiment API and
private field editor; the admin form does not expose field-schema editing.
