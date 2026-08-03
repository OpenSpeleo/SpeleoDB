# Test lint suppressions

- For complexity rules that only flag pytest fixture-heavy test signatures,
  prefer a targeted `# noqa` over changing the test's calling convention.
