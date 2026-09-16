# Inspect effective GitLab authorization after a protection change

A passing run does not rule out server-side cache races. The local GitLab 18.7
service returned no protection rules but cached `ProtectedBranch.protected?` as
true after deleting the default branch rule. Its owner token could push to the
project but failed `can_push_to_branch?`. Invalidate only the affected project's
stale cache through GitLab's own service, then verify effective authorization.

Disposable local test repositories need unprotected branches for lease resets.
Configure that default on their dedicated test group during existing bootstrap,
instead of adding upload retries, new names, or an alternate creation path. Do
not start another pytest process while the user's run is active.
