# Verify the live toolbar order

- [x] Reproduce the stale button order in an HTTP response from the running
      server.
- [x] Refresh the development server and verify the served desktop/mobile
      toolbar.
- [x] Record the cause and verification so source-only checks are not mistaken
      for live UI checks.

The existing runserver used `--noreload` and Django's cached template loader.
Before restart, the real HTTP response placed Import GPS at character 39572 and
Create Geometry at 40305, despite the corrected source order. Restarted the same
development server with automatic reload enabled. Chromium verified Create
Geometry left of Import GPS at 1440, 390, and 320 px, with both controls
visible, no overflow, and the current manifest stylesheet served. Temporary QA
user and session removed. No application logic changes were needed.
