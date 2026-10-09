import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));
// /app is the web bind-mount alias in the monorepo devcontainer.
const monorepo = resolve(root) === '/app' ? '/workspace' : resolve(root, '../..');
const helper = resolve(monorepo, 'utilities/bun-lock/lock.mjs');
if (!existsSync(helper)) {
    console.error('bun run lock requires the SpeleoDB monorepo. In a standalone clone, use bun install --lockfile-only --ignore-scripts.');
    process.exit(1);
}
const result = spawnSync(process.execPath, [helper, ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
