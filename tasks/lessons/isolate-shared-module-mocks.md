# Isolate mocks of shared standard-library modules

A retry test patched `helpers.time.sleep`, which changed the shared stdlib
module and intercepted `subprocess.Popen.wait` polling. A completed commit was
correctly protected against retries, but process cleanup made the test fail.

- Patch the consuming module's reference (`helpers.time`) when spying on only
  its sleep calls, or use an existing injected sleep callable.
- A dotted mock path does not isolate mutations to a shared module object.
- Preserve real sleeps and monotonic clocks in subprocess lifecycle tests.
- Check operation call counts and observable effects in addition to retry sleep
  counts; keep positive retry assertions intact.
