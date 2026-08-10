# Feature Tests Must Exercise Real Boundaries

For feature work in SpeleoDB, do not introduce monkeypatching or module mocks to
simulate storage, ORM failures, controller dependencies, HTTP responses, or
rendered UI state.

- Corrupt or replace files through the configured storage backend.
- Exercise authorization and mutations through real API requests and database
  rows.
- Render real Django templates through the test client.
- Keep frontend rendering logic directly callable so capability and XSS output
  can be tested without replacing its dependencies.
- Prefer an omitted artificial-failure test over a mocked test that claims to
  prove transaction behavior it did not actually execute end to end.

This keeps the test suite aligned with the production integration path and
prevents mocks from validating a different system than the one users run.
