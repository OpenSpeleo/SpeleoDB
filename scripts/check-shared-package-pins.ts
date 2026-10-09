import { readFileSync } from 'node:fs';

const manifest = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')) as { dependencies?: Record<string, string>; overrides?: Record<string, string> };
const names = ['@speleodb/map-core', '@speleodb/map-viewer'];
for (const name of names) {
    const dependency = manifest.dependencies?.[name];
    if (typeof dependency !== 'string' || !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(dependency)) {
        console.error(`${name} must pin an exact stable npm version (for example, 0.1.0).`);
        process.exitCode = 1;
    }
}

if (manifest.overrides?.['@speleodb/map-core'] !== manifest.dependencies?.['@speleodb/map-core']) {
    console.error('The map-core override must exactly match its direct dependency.');
    process.exitCode = 1;
}
