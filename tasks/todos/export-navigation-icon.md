# Export navigation icon

- [x] Add the cloud-download icon to the desktop Export / Backup link, matching
      the sidebar's spacing and active/inactive icon colors.
- [x] Remove the temporary label marker and check both responsive links.
- [x] Run the JavaScript suite and lint inside Docker; review the final diff.
- [x] Increase both icon strokes from 2 to 2.5 at the user's request.
- [x] Mirror the desktop's Backup your data group in the mobile dropdown using
      the existing mobile section styles.

## Review

The initial icon change passed 986 JavaScript tests, JavaScript lint, and Django
template compilation before the user's stop instruction. The subsequent stroke
adjustment was reviewed directly in the patch; no tests or Docker commands were
run for it, as requested.

Mobile now groups Export / Backup under Backup your data between Account
Settings and Feedback, matching the desktop order and reusing mobile section
styling. Reviewed the markup directly; no tests or Docker commands were run.
