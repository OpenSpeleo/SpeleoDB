# Lesson: Soft Delete Must Preserve Dataset Membership

When deleting a permissioned aggregate, do not silently move child records back
into personal ownership unless the product explicitly asks for that behavior.

For Landmark Collections:

- Soft-deleting a collection deactivates the collection and active permissions.
- Member Landmarks keep their `collection_id`.
- Visibility is denied because the collection is inactive.
- Do not unassign member Landmarks; that leaks collaborative records back into
  personal Landmark lists and changes dataset meaning.
