release: python /app/manage.py migrate && bash /app/bin/post_compile
web: bash /app/bin/post_compile && gunicorn config.wsgi:application
worker: REMAP_SIGTERM=SIGQUIT celery -A config.celery_app worker --loglevel=info
beat: REMAP_SIGTERM=SIGQUIT celery -A config.celery_app beat --loglevel=info