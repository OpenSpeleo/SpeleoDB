# Keep service-specific Railway variables on their service

The user corrected placing all Kanchi settings in shared environment variables.
Only use environment-wide shared variables for values that require that scope;
multiple consumers can reference a variable on its owning service directly. This
rollout requires no environment-wide shared variables. Kanchi database
credentials, login configuration, session/token secrets, and allowed
hosts/origins belong directly on Kanchi. The web dashboard link belongs on the
web service. Preserve sensitive local variables in IaC with preserve(); never
promote them to shared scope merely because a prepared authoring file used
shared references.

When moving a variable, preserve its existing value, verify the destination,
then remove the shared copy. Inspect pending dashboard changes as well as live
variables so an operator's in-progress settings are not lost or recreated.

The user also corrected storing resolved infrastructure connection strings as
copied values. A variable being consumed in several places does not justify
copying its owner's credentials into project-wide storage. Prefer direct service
references to the owning Redis/PostgreSQL service. Compose a dedicated Kanchi
database URL from its own database credentials and a reference to PostgreSQL's
private hostname, using its private port. Inspect existing host/port variables:
they may describe a public proxy instead. Diagnose failed nested references;
never replace them with copied URLs as the final design. Verify both raw
reference expressions and rendered values, keeping credentials out of output.
