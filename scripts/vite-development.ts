import fs from 'node:fs';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import type { Manifest, Plugin } from 'vite';

const pendingManifest = '.vite/manifest.pending.json';
const stagingPrefix = '.vite/pending/assets';

/** Publish only a complete immutable generation; the manifest is the commit marker. */
export function publishDevelopmentManifest(outputRoot: string, sources: string[], prefix: string) {
    const pending = path.join(outputRoot, pendingManifest);
    const manifest = JSON.parse(fs.readFileSync(pending, 'utf8')) as Manifest;
    for (const source of sources) {
        if (!manifest[source]?.isEntry) throw new Error(`Missing development entry: ${source}`);
    }
    for (const entry of Object.values(manifest)) {
        for (const dependency of [...(entry.imports ?? []), ...(entry.dynamicImports ?? [])]) {
            if (!manifest[dependency]) throw new Error(`Missing development import: ${dependency}`);
        }
        for (const file of [entry.file, ...(entry.css ?? []), ...(entry.assets ?? [])]) {
            if (!file.startsWith(`${prefix}/`) || file.split('/').includes('..')) {
                throw new Error(`Asset outside development generation: ${file}`);
            }
            if (!fs.statSync(path.join(outputRoot, file)).isFile()) {
                throw new Error(`Missing development output: ${file}`);
            }
        }
    }
    fs.renameSync(pending, path.join(outputRoot, '.vite/manifest.json'));
}

export function developmentPublication(root: string, sources: string[]) {
    const session = randomUUID();
    let generation = 0;
    let outputRoot = '';
    const prefix = () => `assets/dev/${session}/${generation}`;
    const outputNames = () => ({
        entryFileNames: `${stagingPrefix}/[name]-[hash].js`,
        chunkFileNames: `${stagingPrefix}/chunks/[name]-[hash].js`,
        assetFileNames: `${stagingPrefix}/[name]-[hash][extname]`,
    });
    const plugin: Plugin = {
        name: 'speleodb-development-publication',
        enforce: 'post',
        configResolved(config) { outputRoot = path.resolve(config.root, config.build.outDir); },
        buildStart() {
            generation++;
            // Watch templates even when their change introduces no Tailwind candidate.
            for (const app of ['frontend_common', 'frontend_errors', 'frontend_private', 'frontend_public', 'speleodb']) {
                const directory = path.join(root, app, 'templates');
                if (!fs.existsSync(directory)) continue;
                this.addWatchFile(directory);
                for (const entry of fs.readdirSync(directory, { recursive: true, withFileTypes: true })) {
                    this.addWatchFile(path.join(entry.parentPath, entry.name));
                }
            }
        },
        outputOptions(options) { return { ...options, ...outputNames() }; },
        writeBundle: {
            order: 'post',
            sequential: true,
            handler(_options, bundle) {
                // Vite retains unchanged worker bundles between watch builds.
                // Compile into a stable staging tree, then copy the complete
                // relative graph unchanged into this immutable generation.
                // Relative ESM/worker/CSS URLs keep the same relationships.
                const publishedPath = (file: string) => {
                    if (!file.startsWith(`${stagingPrefix}/`)) throw new Error(`Unstaged development asset: ${file}`);
                    return `${prefix()}/${file.slice(stagingPrefix.length + 1)}`;
                };
                fs.mkdirSync(path.join(outputRoot, prefix()), { recursive: true });
                for (const file of Object.keys(bundle)) {
                    if (!file.startsWith(`${stagingPrefix}/`)) continue;
                    const destination = path.join(outputRoot, publishedPath(file));
                    fs.mkdirSync(path.dirname(destination), { recursive: true });
                    fs.copyFileSync(path.join(outputRoot, file), destination);
                }
                const pending = path.join(outputRoot, pendingManifest);
                const manifest = JSON.parse(fs.readFileSync(pending, 'utf8')) as Manifest;
                for (const entry of Object.values(manifest)) {
                    entry.file = publishedPath(entry.file);
                    if (entry.css) entry.css = entry.css.map(publishedPath);
                    if (entry.assets) entry.assets = entry.assets.map(publishedPath);
                }
                fs.writeFileSync(pending, JSON.stringify(manifest, null, 2));
                publishDevelopmentManifest(outputRoot, sources, prefix());
            },
        },
    };
    return {
        manifest: pendingManifest,
        plugin,
        workerPlugin: (): Plugin => ({
            name: 'speleodb-development-worker-generation',
            outputOptions(options) { return { ...options, ...outputNames() }; },
        }),
    };
}
