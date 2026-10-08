import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { State } from '../../state.ts';
import { Layers } from '../layers.ts';
import { publishDisplayEvent } from './display_events.ts';

describe('display event contracts', () => {
    afterEach(() => vi.restoreAllMocks());

    it('dispatches detail-free events only on Window with the existing non-bubbling defaults', () => {
        const documentListener = vi.fn();
        const dispatch = vi.spyOn(window, 'dispatchEvent');
        const events: Event[] = [];
        const listener = (event: Event) => events.push(event);
        document.addEventListener('speleo:display-update-pending', documentListener);
        window.addEventListener('speleo:display-update-pending', listener);
        try {
            publishDisplayEvent({ type: 'speleo:display-update-pending' });
            expect(events).toHaveLength(1);
            // Observe the owning Window method rather than Vitest's global proxy identity.
            expect(dispatch).toHaveBeenCalledExactlyOnceWith(events[0]);
            expect((events[0] as CustomEvent<null>).detail).toBeNull();
            expect(events[0]!.bubbles).toBe(false);
            expect(events[0]!.cancelable).toBe(false);
            expect(documentListener).not.toHaveBeenCalled();
        } finally {
            document.removeEventListener('speleo:display-update-pending', documentListener);
            window.removeEventListener('speleo:display-update-pending', listener);
        }
    });

    it('retains preference and error payload identities', () => {
        const dispatch = vi.spyOn(window, 'dispatchEvent');
        Layers.emitDisplayPreferencesChanged();
        const preferencesEvent = dispatch.mock.calls[0]![0] as CustomEvent<{ preferences: typeof State.displayPreferences }>;
        expect(preferencesEvent.detail.preferences).toBe(State.displayPreferences);
        const detail = { error: new Error('Existing failure') };
        publishDisplayEvent({ type: 'speleo:display-update-failed', detail });
        expect((dispatch.mock.calls[1]![0] as CustomEvent<typeof detail>).detail).toBe(detail);
    });

    it('preserves depth event order and shares the same detail object between both names', () => {
        const dispatch = vi.spyOn(window, 'dispatchEvent');
        const domain = { min: 0, max: 25 };
        State.activeDepthDomain = domain;
        try {
            Layers.emitDepthDomainUpdated();
            expect(dispatch.mock.calls.map(([event]) => event.type)).toEqual([
                'speleo:depth-domain-updated', 'speleo:depth-data-updated',
            ]);
            const first = dispatch.mock.calls[0]![0] as CustomEvent<{ domain: typeof domain }>;
            const second = dispatch.mock.calls[1]![0] as CustomEvent<typeof first.detail>;
            expect(first.detail).toBe(second.detail);
            expect(first.detail.domain).toBe(domain);
        } finally {
            State.activeDepthDomain = null;
        }
    });

    it('accepts valid events and rejects mismatched names and payloads with the native compiler', () => {
        const root = process.cwd();
        const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-display-event-canary-'));
        const module = path.join(root, 'frontend_private/static/private/ts/map_viewer/map/layers/display_events.ts');
        try {
            fs.symlinkSync(path.join(root, 'node_modules'), path.join(directory, 'node_modules'));
            const source = path.join(directory, 'canary.ts');
            const config = path.join(directory, 'tsconfig.json');
            fs.writeFileSync(config, JSON.stringify({
                extends: path.join(root, 'tsconfig.json'),
                compilerOptions: { rootDir: '/', tsBuildInfoFile: path.join(directory, 'canary.tsbuildinfo') },
                files: [source],
                include: [module, path.join(root, 'ts-types/domain/map-display-events.ts'), path.join(root, 'ts-types/domain/map-display.ts')],
            }));
            const check = (calls: string) => {
                fs.writeFileSync(source, `import { publishDisplayEvent } from ${JSON.stringify(module)};\n${calls}`);
                return spawnSync(process.execPath, [path.join(root, 'node_modules/@typescript/native/bin/tsc'), '-p', config], {
                    cwd: root, encoding: 'utf8', timeout: 60_000,
                });
            };
            const valid = check(`publishDisplayEvent({ type: 'speleo:display-update-pending' });
publishDisplayEvent({ type: 'speleo:color-mode-changed', detail: { mode: 'depth' } });
publishDisplayEvent({ type: 'speleo:depth-data-updated', detail: { domain: null, available: false, max: null } });`);
            expect(valid.error).toBeUndefined();
            expect(valid.status, valid.stdout + valid.stderr).toBe(0);
            const invalid = check(`publishDisplayEvent({ type: 'speleo:display-update-pending', detail: {} });
publishDisplayEvent({ type: 'speleo:color-mode-changed', detail: { mode: 'invalid' } });
publishDisplayEvent({ type: 'speleo:depth-data-updated', detail: { domain: null, available: false, max: 'deep' } });
publishDisplayEvent({ type: 'speleo:refresh-cylinder-installs' });`);
            expect(invalid.error).toBeUndefined();
            expect(invalid.status, invalid.stdout + invalid.stderr).toBe(1);
            for (const line of [2, 3, 4, 5]) expect(invalid.stdout).toContain(`canary.ts(${line},`);
        } finally {
            fs.rmSync(directory, { recursive: true, force: true });
        }
    }, 120_000);
});
