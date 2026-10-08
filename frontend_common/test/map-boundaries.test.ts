// @vitest-environment node
import { runtimeClosure } from './runtime-import-graph.ts';
import path from 'node:path';

const viewer = path.resolve('frontend_private/static/private/ts/map_viewer') + path.sep;

it('keeps escaping, CSRF policy and notification beneath the stateful Config/API boundary', () => {
    for (const entry of ['utils.ts', 'components/notification.ts', 'csrf.ts', 'defaults.ts']) {
        const dependencies = runtimeClosure(viewer + entry);
        expect(dependencies.has(viewer + 'config.ts'), entry).toBe(false);
        expect(dependencies.has(viewer + 'api.ts'), entry).toBe(false);
    }
    expect(runtimeClosure(viewer + 'config.ts').has(viewer + 'api.ts')).toBe(true);
    expect(runtimeClosure(viewer + 'api.ts').has(viewer + 'config.ts')).toBe(false);
});

it('keeps request mechanics independent of presentation, state and runtime CSRF lookup', () => {
    expect([...runtimeClosure(viewer + 'transport.ts')]).toEqual([viewer + 'transport.ts']);
    for (const file of ['html.ts', 'url.ts', 'color.ts']) {
        expect([...runtimeClosure(`frontend_common/security/${file}`)]).toEqual([path.resolve(`frontend_common/security/${file}`)]);
    }
});
