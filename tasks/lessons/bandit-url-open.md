# Bandit URL-Open Findings

## Lesson

Ruff's `# noqa` comments do not address Bandit findings, and suppressing B310
would leave the underlying unsafe-scheme capability in place. Integration tests
that consume generated URLs still need an explicit transport boundary.

## Rules

- Do not use `urllib.request.urlopen` for generated or externally shaped URLs.
- Parse the URL before opening a connection, allowlist only `http` and `https`,
  and require a hostname.
- Use the matching `HTTPConnection` or `HTTPSConnection` with a finite timeout.
- Add negative tests for unsupported schemes and missing hostnames.
- Run the actual Bandit hook after security-sensitive test changes; Ruff's
  security rules are complementary, not a substitute.
