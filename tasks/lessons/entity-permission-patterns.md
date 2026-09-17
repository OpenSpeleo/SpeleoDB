# Keep permission abstractions consistent with the repository

The user rejected a new GIS-only generic permission view because its name and
dynamic model/field configuration obscured straightforward sharing behavior
while leaving equivalent GPS Track and other entity views outside the
abstraction.

Before extracting permission infrastructure, inspect all existing entity
patterns. Prefer their concrete, typed view and serializer style when a proposed
base would serve only a subset without a coherent boundary. Reuse established
cross-entity validation helpers and keep authorization and transaction scope
visible at the model-specific endpoint. Do not turn a feature request into an
unrequested permissions-framework migration.
