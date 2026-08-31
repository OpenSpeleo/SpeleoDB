# Separate container and browser service addresses

When moving local services from host networking to a Compose network, audit
every inherited service, including one-shot setup containers. A setup service
that retains `network_mode: host` can prevent a fresh stack from starting on
Docker Desktop even when the long-running application services are correct.

Provisioning addresses and persisted browser-facing addresses are separate
concerns. Use Compose DNS for container-to-container operations, but preserve
`localhost` values written into developer-facing configuration when the browser
must access a published host port.

Test settings that reload standalone environment files need the same audit.
Provide explicit devcontainer test endpoints after that reload rather than
changing the standalone test configuration to Compose-only hostnames.
