# Railway terminates public TLS; Omnibus NGINX receives internal HTTP.
external_url ENV.fetch('GITLAB_EXTERNAL_URL')
gitlab_rails['nginx']['listen_port'] = Integer(ENV.fetch('PORT', '8080'))
gitlab_rails['nginx']['listen_https'] = false
letsencrypt['enable'] = false

# This instance serves API/Git integration tests, with bundled PostgreSQL,
# Redis and Gitaly. Keep enough concurrency for overlapping test runs.
puma['worker_processes'] = 2
# Omnibus defaults Puma's loopback TCP listener to 8080 as well. Workhorse uses
# its Unix socket, but that optional listener must not collide with NGINX.
puma['port'] = 8081
sidekiq['concurrency'] = 10
postgresql['shared_buffers'] = '256MB'
prometheus_monitoring['enable'] = false
gitlab_kas['enable'] = false
registry['enable'] = false
gitlab_pages['enable'] = false
gitlab_rails['gitlab_email_enabled'] = false
gitlab_rails['display_initial_root_password'] = false
gitlab_rails['store_initial_root_password'] = false
