import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
if (process.env.SPELEODB_LOCAL_PACKAGES === '1') {
    for (const name of ['@speleodb/map-core', '@speleodb/map-viewer']) {
        let manifest: { speleodbLocalSources?: boolean };
        try {
            manifest = JSON.parse(readFileSync(require.resolve(`${name}/package.json`), 'utf8')) as typeof manifest;
        } catch {
            throw new Error(`Local package ${name} is missing. Run the monorepo devcontainer package installer; no remote fallback is permitted.`);
        }
        if (manifest.speleodbLocalSources !== true) {
            throw new Error(`Local package ${name} requires the monorepo source overlay.`);
        }
    }
}

export const sharedMapResolution = {
    // Compatibility with existing Git pins; new package exports default to source.
    conditions: ['speleodb-source', 'module', 'browser', 'development|production'],
    dedupe: ['maplibre-gl', '@speleodb/map-core', '@speleodb/map-viewer'],
    preserveSymlinks: true,
};
