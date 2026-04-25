# Django Stubs Model Drift

When a feature changes model ownership or removes a model field, run mypy before
calling the work done. Django-stubs catches stale query fields and stale object
attributes that normal runtime tests may not touch, especially after model
redesigns.

Do not hide these with broad ignores. Fix the drift at the source:

- Remove or rewrite obsolete permission classes that still reference removed
  fields.
- Prefer real type narrowing (`isinstance`, authenticated-user guards, casts at
  framework boundaries) over `type: ignore`.
- For Django test responses, assert the concrete redirect type before reading
  redirect-only attributes like `.url`.
- For factory-boy declarations, type the factory descriptor when Django-stubs
  cannot treat the declaration as the produced model instance.
