# Persistent Dependency Volumes Need One Writer Identity

A named `node_modules` volume does not solve host/container platform isolation
by itself. A fresh Docker volume is normally root-owned, and a root-running
webserver can populate `.vite-temp` before an interactive devcontainer user runs
a build. The shared files then exist on Linux but remain unwritable.

For SpeleoDB local development:

- exclude host `node_modules` from the Docker build context;
- make the image mount point owned by `dev-user`;
- let the root setup job migrate a legacy volume only when its root owner is
  wrong; and
- run every normal npm/Vite writer as `dev-user`.

Keep Dev Containers from rewriting only the interactive service's numeric UID.
The same username with different UIDs across setup, workspace, and webserver is
still a conflicting-writer architecture on a shared volume.

Do not repair this with repeated recursive `chown`, `sudo rm`, or a manual
`npm ci`. Those actions hide the conflicting-writer architecture and make the
problem return on the next rebuild.
