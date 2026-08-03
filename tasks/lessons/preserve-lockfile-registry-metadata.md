# Preserve Registry Metadata During Lockfile Updates

## Correction

A dependency refresh rewrote the committed root lockfile from npm's hidden
installed-tree lock. Unchanged registry packages kept their versions but lost
`resolved` and `integrity`, weakening reproducibility and breaking the compiler
dependency contract.

## Rule

Generate the committed `package-lock.json` independently of `node_modules` and
its hidden `.package-lock.json`. After any dependency update, verify that every
registry-backed package node still contains a supported integrity checksum and
that no unrelated graph metadata disappeared. Never silence the integrity
contract to accommodate a metadata-poor lockfile.
