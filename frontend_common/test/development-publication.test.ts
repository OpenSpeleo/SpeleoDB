// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { publishDevelopmentManifest } from '../../scripts/vite-development.ts';

describe('development publication', () => {
    let root: string;
    const source = 'frontend_common/app.ts';
    beforeEach(() => {
        root = mkdtempSync(path.join(tmpdir(), 'speleodb-publication-'));
        mkdirSync(path.join(root, '.vite'));
    });
    afterEach(() => { rmSync(root, { recursive: true, force: true }); });
    function pending(generation: number) {
        const prefix = `assets/dev/session/${generation}`;
        mkdirSync(path.join(root, prefix), { recursive: true });
        for (const name of ['app.js', 'worker.js', 'style.css']) writeFileSync(path.join(root, prefix, name), String(generation));
        const manifest = {
            [source]: { file: `${prefix}/app.js`, isEntry: true, css: [`${prefix}/style.css`], assets: [`${prefix}/worker.js`] },
        };
        writeFileSync(path.join(root, '.vite/manifest.pending.json'), JSON.stringify(manifest));
        return prefix;
    }
    it('publishes rapid complete generations while keeping old lazy assets', () => {
        publishDevelopmentManifest(root, [source], pending(1));
        const first = readFileSync(path.join(root, '.vite/manifest.json'), 'utf8');
        const prefix = pending(2);
        expect(readFileSync(path.join(root, '.vite/manifest.json'), 'utf8')).toBe(first);
        publishDevelopmentManifest(root, [source], prefix);
        expect(readFileSync(path.join(root, '.vite/manifest.json'), 'utf8')).toContain('/session/2/');
        expect(readFileSync(path.join(root, 'assets/dev/session/1/worker.js'), 'utf8')).toBe('1');
    });
    it('keeps prior publication when output is incomplete or pending JSON is malformed', () => {
        publishDevelopmentManifest(root, [source], pending(1));
        const first = readFileSync(path.join(root, '.vite/manifest.json'), 'utf8');
        const prefix = pending(2);
        rmSync(path.join(root, prefix, 'worker.js'));
        expect(() => publishDevelopmentManifest(root, [source], prefix)).toThrow();
        expect(readFileSync(path.join(root, '.vite/manifest.json'), 'utf8')).toBe(first);
        writeFileSync(path.join(root, '.vite/manifest.pending.json'), '{');
        expect(() => publishDevelopmentManifest(root, [source], prefix)).toThrow();
        expect(readFileSync(path.join(root, '.vite/manifest.json'), 'utf8')).toBe(first);
    });
    it('rejects a missing registered entry or assets from another generation', () => {
        const prefix = pending(1);
        expect(() => publishDevelopmentManifest(root, ['missing'], prefix)).toThrow('Missing development entry');
        expect(() => publishDevelopmentManifest(root, [source], 'assets/dev/session/2')).toThrow('outside development generation');
    });
});
