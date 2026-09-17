# Register and build new Vite entries before live template use

Adding a preload to the shared sidebar before the new controller was available
caused live pages to raise Unknown Vite logical entry. The registry is cached
for the Django process lifetime, so rebuilding alone does not refresh it. When
introducing a new logical entry, register its source and complete the asset
build before exposing it in a shared template. Confirm the running Django
process sees the registry and serves the new manifest entry before reporting the
feature ready. Trigger the development server's autoreload after registry
changes so its process cache is refreshed; do not assume JSON changes trigger
Python autoreload.
