# Background scheduling without Railway cron

When this feature needs periodic dispatch, recovery, notifications, or cleanup,
use the continuously running Celery Beat service and database scheduler. The
user explicitly rejected Railway cron jobs. Do not create a Railway cron
service, set a Railway cron schedule, or describe recurring maintenance as
Railway cron. Railway hosts the long-running workers and scheduler; Beat owns
scheduling.
