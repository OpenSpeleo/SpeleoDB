# Test lint suppressions

- For complexity rules that only flag pytest fixture-heavy test signatures,
  prefer a targeted `# noqa` over changing the test's calling convention.
- Explicit dummy secrets in subprocess tests trigger Ruff S106. Use a line-level
  suppression with a test-only explanation, and run focused lint before
  reporting verification complete. Keep runtime secret requirements unchanged.
