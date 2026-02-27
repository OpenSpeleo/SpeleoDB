# Lesson: Use the ORM — never reinvent filtering or fetching in Python

**Date:** 2026-02-26
**Trigger:** Code review of `speleodb/gis/models/view.py`

## Mistake 1: Materializing a queryset to grab one element

```python
# BAD — materializes the ENTIRE queryset into a Python list, then takes [0]
geojsons = list(project.geojsons.all())
if not geojsons:
    continue
proj_geojson = geojsons[0]
```

```python
# GOOD — lets the database do the work with LIMIT 1
first = project.geojsons.first()
if first is None:
    continue
proj_geojson = first
```

## Mistake 2: Python-side filtering instead of `.filter()`

```python
# BAD — iterates every row in Python to find a match by field value
matched = next(
    (g for g in project.geojsons.all() if g.commit_id == sha),
    None,
)
```

```python
# GOOD — one indexed DB query, zero Python iteration
matched = project.geojsons.filter(commit_id=sha).first()
```

## Rule

**Never reimplement database operations in Python.** The ORM exists to push
work to the database where it belongs. This means:

- Fetching one item: `.first()`, `.last()`, `.get()`
- Filtering by field: `.filter(field=value)`, never a Python generator/loop
- Counting: `.count()`, not `len(list(qs))`
- Existence: `.exists()`, not `bool(list(qs))`
- Slicing: `qs[:5]`, not `list(qs)[0:5]`

## Why it matters

- The database has indexes. Python loops don't.
- `.filter().first()` produces `SELECT ... WHERE commit_id = %s LIMIT 1`
  — a single indexed lookup.
- Python-side iteration loads every row, deserializes every object, then
  throws away all but one. For large tables this is catastrophically slower.
- Even when a prefetch cache exists, writing `filter()` makes the intent
  clear and keeps the code honest when the prefetch is later removed.

## Self-check before committing

1. Am I converting a queryset to a list? Do I need all items?
2. Am I looping/generating over a queryset to find a match? Use `.filter()`.
3. Am I doing `next(... for x in qs if x.field == val)` ? That is always
   wrong — use `.filter(field=val).first()`.
