# Container-only feature verification

## Latest instruction (2026-09-14)

The user explicitly stopped tests and Docker usage during the export icon edits.
For the current UI work, make the requested edits without tests or Docker
commands unless the user asks to resume them. Keep verification proportional to
small visual changes. This instruction supersedes the earlier workflow below.

## Earlier export-feature workflow

The user requires all tests, builds, lint, type checks, and runtime verification
for this export feature to execute inside Docker. Use the repository Compose
environment and isolated test resources. If Docker is stopped, start or repair
it and continue code work while it starts; do not fall back to host tests.
