# Synchronous Upload Does Not Need Job State

When the product owner explicitly requires parsing and conversion to complete
inside the upload request, do not retain speculative queue/build/status
architecture from an earlier design exploration.

Rules:

- Model the selected product workflow, not every future scaling option.
- A synchronous converted-format upload returns success only after conversion,
  source persistence, display-file persistence, and database publication finish.
- Validation or conversion failure creates no aggregate and no durable object.
- Do not add `QUEUED`, `PROCESSING`, retry endpoints, polling UI, Celery
  routing, worker deployment, or stuck-job recovery when there is no
  asynchronous job.
- Keep the implementation limited to the source object and one display object;
  add versioning only when a concrete product requirement needs it.
- S3 is still non-transactional: track objects written during the request and
  explicitly delete them if later persistence fails.

Origin: the GIS Layers implementation initially carried the planning brief's
async working hypothesis into code after the owner selected synchronous upload.
The correction was to remove that state entirely, not merely hide it in the UI.
