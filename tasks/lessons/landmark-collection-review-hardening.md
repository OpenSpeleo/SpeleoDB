# Landmark Collection Review Hardening

Rules from the adversarial Landmark Collection review:

1. Catching `IntegrityError` is not enough inside Django tests or outer
   transactions. Wrap the risky save in `transaction.atomic()` so the rollback
   is contained in a savepoint before returning a 400.
2. Soft-deleted collection rows must disappear at object boundaries. Filter
   object/detail/export/permission/member Landmark querysets by active
   collection, and keep ordinary active-object permission denials as 403.
3. Public serializers should not expose lifecycle flags as writable fields.
   `is_active` belongs to soft delete, not create/update payloads.
4. Revoked permission rows are inactive history. `PUT` should update active
   permission rows only; `POST` owns reactivation semantics.
5. Import endpoints must validate collection access before object creation and
   create Landmarks in one transaction so failed imports leave no partial rows.
6. OGC child links must be built from `request.path`, not `get_full_path()`, or
   query parameters such as `?f=json` will corrupt discoverable URLs.
7. Frontend read-only controls need absence, not disabled theater. Hide edit,
   delete, context-menu, and drag affordances unless the API state says the user
   can write/delete.
