# Verify subprocess and integration tests against the CI environment

Local Compose credentials and private dotenv files can hide missing CI inputs.
GitHub Actions service environment variables configure the service container;
runner-side integration tests need their own explicit connection variables.

A default in Django test settings does not populate `os.environ`. Tests that
launch a subprocess with another settings module must supply that module's
required inputs, disable private dotenv loading, and include captured stderr in
failure assertions.

Reproduce CI failures from a disposable tracked checkout with the workflow's
environment before fixing them. Re-run the same behavioral tests afterward,
including real database provisioning when that is the contract under test.
