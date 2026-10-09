// @vitest-environment node
import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

describe('monorepo bun run lock entrypoint', () => {
    let directory: string;
    let workspace: string;
    let web: string;
    let helper: string;

    beforeEach(() => {
        directory = mkdtempSync(join(tmpdir(), 'speleodb-lock-launcher-test-'));
        workspace = join(directory, 'monorepo');
        web = join(workspace, 'apps', 'web');
        helper = join(workspace, 'utilities', 'bun-lock', 'lock.mjs');
        mkdirSync(join(web, 'scripts'), { recursive: true });
        mkdirSync(join(workspace, 'utilities', 'bun-lock'), { recursive: true });
        writeFileSync(join(workspace, 'package.json'), JSON.stringify({
            private: true,
            workspaces: ['apps/*'],
            dependencies: { 'must-not-resolve': 'file:./missing' },
        }));
        writeFileSync(join(workspace, 'bun.lock'), 'parent lock sentinel');
        writeFileSync(join(web, 'bun.lock'), 'child lock sentinel');
        writeFileSync(join(web, 'package.json'), JSON.stringify({
            name: 'web-fixture',
            private: true,
            scripts: { lock: 'bun scripts/lock.ts' },
        }));
        copyFileSync(new URL('../../scripts/lock.ts', import.meta.url), join(web, 'scripts', 'lock.ts'));
    });

    afterEach(() => rmSync(directory, { recursive: true, force: true }));

    const run = (...args: string[]) => spawnSync(process.execPath, ['run', 'lock', ...args], {
        cwd: web, encoding: 'utf8', timeout: 30_000,
    });

    it.each([
        { args: [], forwarded: [] },
        { args: ['--upgrade'], forwarded: ['--upgrade'] },
        // Bun consumes the run command's separator before invoking the script.
        { args: ['--', '--upgrade'], forwarded: ['--upgrade'] },
        { args: ['--unknown'], forwarded: ['--unknown'] },
    ])('forwards arguments $args and the package directory to the shared helper', ({ args, forwarded }) => {
        writeFileSync(helper, `import { writeFileSync } from 'node:fs';
writeFileSync('invocation.json', JSON.stringify({ cwd: process.cwd(), args: process.argv.slice(2) }));`);
        const result = run(...args);
        expect(result.status, result.stderr + result.stdout).toBe(0);
        expect(JSON.parse(readFileSync(join(web, 'invocation.json'), 'utf8'))).toEqual({ cwd: web, args: forwarded });
        expect(readFileSync(join(workspace, 'bun.lock'), 'utf8')).toBe('parent lock sentinel');
        expect(readFileSync(join(web, 'bun.lock'), 'utf8')).toBe('child lock sentinel');
    });

    it('propagates resolver failures', () => {
        writeFileSync(helper, 'process.exit(42);');
        expect(run('--upgrade').status).toBe(42);
        expect(readFileSync(join(web, 'bun.lock'), 'utf8')).toBe('child lock sentinel');
    });

    it('fails clearly without modifying locks when the monorepo helper is absent', () => {
        const result = run('--upgrade');
        expect(result.status).toBe(1);
        expect(result.stderr).toContain('requires the SpeleoDB monorepo');
        expect(result.stderr).not.toContain('Cannot find module');
        expect(result.stderr).not.toContain(' at ');
        expect(readFileSync(join(web, 'bun.lock'), 'utf8')).toBe('child lock sentinel');
        expect(readFileSync(join(workspace, 'bun.lock'), 'utf8')).toBe('parent lock sentinel');
        expect(existsSync(join(web, 'node_modules'))).toBe(false);
    });
});
