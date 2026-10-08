import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import { developmentPublication } from './scripts/vite-development.ts';
type EntryRegistry = typeof import('./frontend_common/entries.json');

const rootDirectory = path.dirname(fileURLToPath(import.meta.url));
const registryPath = path.join(rootDirectory, 'frontend_common', 'entries.json');
const registry = JSON.parse(fs.readFileSync(registryPath, 'utf8')) as EntryRegistry;
const sourceEntries = { ...registry.styles, ...registry.scripts };

function resolvedEntries() {
    return Object.fromEntries(
        Object.entries(sourceEntries).map(([name, sourcePath]) => [
            name,
            path.resolve(rootDirectory, sourcePath),
        ]),
    );
}

export default defineConfig(({ mode }) => {
    const production = mode === 'production';
    const development = production ? null : developmentPublication(rootDirectory, Object.values(sourceEntries));

    return {
        base: './',
        clearScreen: false,
        plugins: [tailwindcss(), ...(development ? [development.plugin] : [])],
        worker: development ? { plugins: () => [development.workerPlugin()] } : {},
        build: {
            target: 'baseline-widely-available',
            outDir: path.resolve(
                rootDirectory,
                'speleodb/common/static/speleodb/vite',
            ),
            emptyOutDir: production,
            manifest: development?.manifest ?? true,
            minify: production,
            cssMinify: production ? 'lightningcss' : false,
            sourcemap: !production,
            cssCodeSplit: true,
            modulePreload: { polyfill: false },
            rolldownOptions: {
                input: resolvedEntries(),
                output: {
                    entryFileNames: production
                        ? 'assets/[name]-[hash].js'
                        : 'assets/[name].js',
                    chunkFileNames: 'assets/chunks/[name]-[hash].js',
                    assetFileNames: production
                        ? 'assets/[name]-[hash][extname]'
                        : 'assets/[name][extname]',
                },
            },
        },
    };
});
