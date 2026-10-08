import { readFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')) as { dependencies?: Record<string, string>; overrides?: Record<string, string> };
const names = ['@speleodb/map-core', '@speleodb/map-viewer'];
for (const name of names) {
    const dependency = manifest.dependencies?.[name];
    if (typeof dependency !== 'string' || !/^git\+https:\/\/github\.com\/[^/]+\/[^#]+#[a-f0-9]{40}$/.test(dependency)) {
        console.error(`Standalone release unavailable: ${name} needs its public GitHub URL and full 40-character commit SHA. Use a reachable published revision; local development uses the monorepo source overlay. These packages are not distributed through npm.`);
        process.exitCode = 1;
    }
}

if (manifest.overrides?.['@speleodb/map-core'] !== manifest.dependencies?.['@speleodb/map-core']) {
    console.error('The map-core Bun override must exactly match its direct Git pin, so viewer peer resolution never falls back to npm.');
    process.exitCode = 1;
}
