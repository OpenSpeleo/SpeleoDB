// @vitest-environment node
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { checkSharedPackageCI } from '../../scripts/check-shared-package-ci.ts';

const core = 'a'.repeat(40);
const viewer = 'b'.repeat(40);
const corePin = `git+https://github.com/OpenSpeleo/SpeleoDB-TS-MapCore.git#${core}`;
const manifest = () => ({
    dependencies: {
        '@speleodb/map-core': corePin,
        '@speleodb/map-viewer': `git+https://github.com/OpenSpeleo/SpeleoDB-TS-MapViewer.git#${viewer}`,
    },
    overrides: { '@speleodb/map-core': corePin },
});
const run = (sha: string, status = 'completed', conclusion: string | null = 'success', id = 1) => ({
    id, head_sha: sha, event: 'push', status, conclusion,
    html_url: `https://github.com/OpenSpeleo/package/actions/runs/${id}`,
});

type Reply = { status?: number; body: unknown };
function fixture(reply?: (url: URL, round: number) => Reply | undefined) {
    let elapsed = 0;
    let round = 0;
    const calls: URL[] = [];
    const sleeps: number[] = [];
    const logs: string[] = [];
    const runtime = {
        now: () => elapsed,
        sleep: async (ms: number) => { sleeps.push(ms); elapsed += ms; round++; },
        log: (message: string) => { logs.push(message); },
        fetch: async (input: string, init: RequestInit) => {
            const url = new URL(input);
            calls.push(url);
            expect(url.origin).toBe('https://api.github.com');
            expect(init.signal).toBeInstanceOf(AbortSignal);
            const sha = url.pathname.includes('MapCore') ? core : viewer;
            const result = reply?.(url, round) ?? { body: url.pathname.includes('/commits/')
                ? { sha } : { workflow_runs: [run(sha)] } };
            return new Response(JSON.stringify(result.body), { status: result.status ?? 200 });
        },
    };
    return { runtime, calls, sleeps, logs, advance: (ms: number) => { elapsed += ms; } };
}

describe('published shared package CI gate', () => {
    it('checks both exact commits and their verification workflow before succeeding', async () => {
        const f = fixture();
        await checkSharedPackageCI(manifest(), f.runtime);
        expect(f.calls.map(url => url.pathname)).toEqual([
            `/repos/OpenSpeleo/SpeleoDB-TS-MapCore/commits/${core}`,
            `/repos/OpenSpeleo/SpeleoDB-TS-MapViewer/commits/${viewer}`,
            '/repos/OpenSpeleo/SpeleoDB-TS-MapCore/actions/workflows/ci.yml/runs',
            '/repos/OpenSpeleo/SpeleoDB-TS-MapViewer/actions/workflows/ci.yml/runs',
        ]);
        for (const url of f.calls.slice(2)) {
            expect(url.searchParams.get('head_sha')).toBe(url.pathname.includes('MapCore') ? core : viewer);
            expect(url.searchParams.get('event')).toBe('push');
        }
        expect(f.sleeps).toEqual([]);
    });

    it.each(['master', core.slice(0, 8), `${core}extra`])('rejects nonimmutable pin %s before network access', async sha => {
        const m = manifest();
        m.dependencies['@speleodb/map-viewer'] = m.dependencies['@speleodb/map-viewer'].replace(viewer, sha);
        const f = fixture();
        await expect(checkSharedPackageCI(m, f.runtime)).rejects.toThrow('full 40-character SHA');
        expect(f.calls).toEqual([]);
    });

    it('rejects foreign repositories and inconsistent core overrides', async () => {
        const m = manifest();
        m.dependencies['@speleodb/map-viewer'] = m.dependencies['@speleodb/map-viewer'].replace('OpenSpeleo', 'other');
        const f = fixture();
        await expect(checkSharedPackageCI(m, f.runtime)).rejects.toThrow('OpenSpeleo');
        m.dependencies = manifest().dependencies;
        m.overrides['@speleodb/map-core'] = 'invalid';
        await expect(checkSharedPackageCI(m, f.runtime)).rejects.toThrow('override');
        expect(f.calls).toEqual([]);
    });

    it.each([404, 422, 403, 500])('fails immediately on HTTP %i, including a missing commit', async status => {
        const f = fixture(() => ({ status, body: {} }));
        await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow(`HTTP ${status}`);
        expect(f.calls).toHaveLength(1);
        expect(f.sleeps).toEqual([]);
    });

    it('rejects a different returned commit SHA', async () => {
        const f = fixture(() => ({ body: { sha: viewer } }));
        await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow('different commit');
    });

    it.each(['failure', 'cancelled', 'timed_out', 'neutral', 'skipped', 'action_required', 'stale', null])(
        'fails immediately for completed CI conclusion %s', async conclusion => {
            const f = fixture(url => url.pathname.includes('/runs')
                ? { body: { workflow_runs: [run(core, 'completed', conclusion)] } } : undefined);
            await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow('verification');
            expect(f.sleeps).toEqual([]);
        },
    );

    it('waits for queued CI and missing runs, then succeeds', async () => {
        const f = fixture((url, round) => {
            if (!url.pathname.includes('/runs') || round > 1) return;
            return { body: { workflow_runs: round === 0 ? [] : [run(
                url.pathname.includes('MapCore') ? core : viewer, 'queued', null,
            )] } };
        });
        await checkSharedPackageCI(manifest(), f.runtime);
        expect(f.sleeps).toEqual([30_000, 30_000]);
    });

    it('does not accept an older green run over a newer failed run', async () => {
        const f = fixture(url => url.pathname.includes('/runs') ? { body: {
            workflow_runs: [run(core), run(core, 'completed', 'failure', 2)],
        } } : undefined);
        await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow('failure');
    });

    it('rechecks green packages while another waits, catching a failed rerun', async () => {
        const f = fixture((url, round) => {
            if (!url.pathname.includes('/runs')) return;
            return { body: { workflow_runs: [url.pathname.includes('MapCore')
                ? run(core, 'completed', round === 0 ? 'success' : 'failure')
                : run(viewer, 'in_progress', null)] } };
        });
        await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow('failure');
        expect(f.sleeps).toEqual([30_000]);
    });

    it.each(['missing', 'pending', 'wrong-sha', 'pull-request'])('bounds %s CI to one shared 30-minute wait', async state => {
        const f = fixture(url => url.pathname.includes('/runs') ? { body: { workflow_runs:
            state === 'missing' ? [] : [{ ...run(state === 'wrong-sha' ? 'c'.repeat(40) : core,
                state === 'pending' ? 'in_progress' : 'completed'),
                event: state === 'pull-request' ? 'pull_request' : 'push' }],
        } } : undefined);
        await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow('within 30 minutes');
        expect(f.sleeps.reduce((sum, ms) => sum + ms, 0)).toBe(30 * 60 * 1000);
    });

    it('includes API time in the deadline and rejects late success', async () => {
        const f = fixture(() => { f.advance(30 * 60 * 1000); return undefined; });
        await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow('within 30 minutes');
        expect(f.sleeps).toEqual([]);
    });

    it('checks all pages before choosing the latest run', async () => {
        const f = fixture(url => url.pathname.includes('/runs') ? { body: { workflow_runs:
            url.searchParams.get('page') === '1'
                ? Array.from({ length: 100 }, (_, id) => run(core, 'completed', 'success', id + 1))
                : [run(core, 'completed', 'failure', 101)],
        } } : undefined);
        await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow('failure');
    });

    it.each([
        {},
        { workflow_runs: [{ ...run(core), id: undefined }] },
        { workflow_runs: [{ ...run(core), status: null }] },
    ])('fails closed on malformed workflow responses: %j', async body => {
        const f = fixture(url => url.pathname.includes('/runs') ? { body } : undefined);
        await expect(checkSharedPackageCI(manifest(), f.runtime)).rejects.toThrow();
    });
});

interface Job {
    needs?: string | string[];
    if?: string;
    'timeout-minutes'?: number;
    permissions?: Record<string, string>;
    steps?: { run?: string; env?: Record<string, string> }[];
}

it('gates every app job before any dependency installation', () => {
    const workflow = JSON.parse(execFileSync(process.execPath, [
        '--eval', 'process.stdout.write(JSON.stringify(Bun.YAML.parse(await Bun.stdin.text())))',
    ], { input: readFileSync('.github/workflows/ci.yml', 'utf8'), encoding: 'utf8' })) as { jobs: Record<string, Job> };
    const jobs = workflow.jobs;
    const gate = jobs['shared-package-ci']!;
    expect(gate.if).toBeUndefined();
    expect(gate['timeout-minutes']).toBe(32);
    expect(gate.permissions).toEqual({ contents: 'read', actions: 'read' });
    expect(gate.steps?.filter(step => step.run).map(({ run, env }) => ({ run, env }))).toEqual([{
        run: 'bun scripts/check-shared-package-ci.ts',
        env: { GITHUB_TOKEN: '${{ github.token }}' },
    }]);
    function dependsOnGate(name: string, visited = new Set<string>()): boolean {
        if (name === 'shared-package-ci') return true;
        if (visited.has(name)) throw new Error(`CI dependency cycle: ${name}`);
        const job = jobs[name]!;
        expect(job.if ?? '').not.toMatch(/(?:always|failure)\s*\(|!\s*cancelled\s*\(/);
        const needs = typeof job.needs === 'string' ? [job.needs] : job.needs ?? [];
        return needs.some(dependency => dependsOnGate(dependency, new Set([...visited, name])));
    }
    for (const name of Object.keys(jobs)) expect(dependsOnGate(name), name).toBe(true);
});
