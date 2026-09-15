# Reuse infrastructure and scale one worker service

The user corrected unnecessary service proliferation in the export feature.
Start with the existing Redis server and PostgreSQL server. Use separate Redis
logical databases for cache/broker and a separate PostgreSQL database/user for
Kanchi. Configure shared Redis durability and eviction explicitly.

Run one Celery worker service consuming both `exports` and `background_control`.
The user will add worker replicas when needed. Do not create dedicated workers
or database servers based on hypothetical future load. Keep one Beat scheduler
and no Railway cron. Document that long tasks can delay maintenance.

When limiting worker queues, set the default queue to one the worker consumes.
Verify an existing task without an explicit queue through the real worker so
bringing exports online does not strand older background jobs.

When the user pauses work for review, keep commits and deployment paused.
Implement only the corrections they authorize during that review.
