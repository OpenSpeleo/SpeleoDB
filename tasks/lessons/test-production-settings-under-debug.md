# Test production-derived settings independently of DEBUG

Settings that exist only inside a `DEBUG=False` branch are unavailable when a
test container enables debug mode. A contract test that reads such a setting
directly will fail before checking the actual invariant.

Compute environment-independent production values unconditionally under an
explicit production-contract name, then assign them to the runtime setting in
the production branch. Tests can validate the derived value in either mode
without weakening the assertion or changing debug behavior.
