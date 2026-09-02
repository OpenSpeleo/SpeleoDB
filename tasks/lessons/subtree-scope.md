# Subtree Scope

When a task is explicitly confined to the web application, validation must stay
inside `apps/web` even when the monorepo exposes convenient aggregate commands.

Do not run root `npm test`, root `npm run build`, or another aggregate target
for a web-only task: those commands enter unrelated application subtrees. Use
the web-local commands from `apps/web` and run that subtree's own `prek run -a`.
Inspect another subtree only when the user explicitly expands the scope.
