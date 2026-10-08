// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { spawn } from 'node:child_process';
import type { ChildProcess } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

describe('development process lifecycle', () => {
    let root: string;
    let supervisor: ChildProcess | undefined;
    beforeEach(() => { root = mkdtempSync(path.join(tmpdir(), 'speleodb-supervisor-')); });
    afterEach(() => {
        supervisor?.kill('SIGKILL');
        rmSync(root, { recursive: true, force: true });
    });
    async function waitForFile(file: string) {
        const deadline = Date.now() + 5000;
        while (!existsSync(file)) {
            if (Date.now() >= deadline) throw new Error(`Child did not initialize: ${file}`);
            await new Promise(resolve => setTimeout(resolve, 20));
        }
    }
    function launch(failure: number | 'spawn' | null = null, descendant = false, stubborn = false) {
        const child = path.join(root, 'child.ts');
        writeFileSync(child, `
            import fs from 'node:fs';
            import { spawn } from 'node:child_process';
            const prefix = process.argv[2];
            if (process.argv[3] === 'parent') spawn(process.execPath, [process.argv[1], prefix + '.descendant', 'descendant'], { stdio: 'ignore' });
            fs.writeFileSync(prefix + '.ready', String(process.pid));
            for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => {
                fs.writeFileSync(prefix + '.signal', signal);
                if (process.argv[3] === 'stubborn') return;
                if (process.argv[3] === 'descendant') setTimeout(() => {
                    fs.writeFileSync(prefix + '.done', 'done');
                    process.exit(0);
                }, 75);
                else process.exit(0);
            });
            setInterval(() => {}, 1000);
        `);
        const commands = [
            { name: 'first', command: process.execPath, args: [child, path.join(root, 'first'), descendant ? 'parent' : stubborn ? 'stubborn' : 'child'] },
            { name: 'second', command: failure === 'spawn' ? path.join(root, 'missing-executable') : process.execPath, args: typeof failure === 'number'
                ? ['-e', `setTimeout(() => process.exit(${failure}), 300)`]
                : [child, path.join(root, 'second')] },
        ];
        const script = path.join(root, 'supervisor.ts');
        writeFileSync(script, `
            import { supervise } from ${JSON.stringify(path.resolve('scripts/dev.ts'))};
            process.exitCode = await supervise(${JSON.stringify(commands)}, 200);
        `);
        supervisor = spawn(process.execPath, [script], { stdio: 'ignore' });
        return new Promise<number | null>((resolve, reject) => {
            supervisor!.once('exit', resolve);
            supervisor!.once('error', reject);
        });
    }
    it.each([['SIGINT', 130], ['SIGTERM', 143]] as const)('forwards %s and awaits both children', async (signal, code) => {
        const exit = launch();
        await Promise.all(['first', 'second'].map(name => waitForFile(path.join(root, `${name}.ready`))));
        supervisor!.kill(signal);
        expect(await exit).toBe(code);
        for (const name of ['first', 'second']) {
            expect(readFileSync(path.join(root, `${name}.signal`), 'utf8')).toBe(signal);
            const pid = Number(readFileSync(path.join(root, `${name}.ready`), 'utf8'));
            expect(() => process.kill(pid, 0)).toThrow();
        }
    });
    it.each([0, 7])('treats unexpected child exit %i as failure and stops the remaining watcher', async code => {
        const exit = launch(code);
        await waitForFile(path.join(root, 'first.ready'));
        expect(await exit).toBe(code || 1);
        expect(readFileSync(path.join(root, 'first.signal'), 'utf8')).toBe('SIGTERM');
    });
    it('signals descendants and waits when their direct watcher exits first', async () => {
        const exit = launch(null, true);
        await waitForFile(path.join(root, 'first.descendant.ready'));
        await waitForFile(path.join(root, 'second.ready'));
        supervisor!.kill('SIGTERM');
        expect(await exit).toBe(143);
        expect(readFileSync(path.join(root, 'first.descendant.signal'), 'utf8')).toBe('SIGTERM');
        expect(readFileSync(path.join(root, 'first.descendant.done'), 'utf8')).toBe('done');
    });
    it('escalates shutdown when a watcher ignores the forwarded signal', async () => {
        const exit = launch(null, false, true);
        await Promise.all(['first', 'second'].map(name => waitForFile(path.join(root, `${name}.ready`))));
        supervisor!.kill('SIGTERM');
        expect(await exit).toBe(143);
        expect(readFileSync(path.join(root, 'first.signal'), 'utf8')).toBe('SIGTERM');
        const pid = Number(readFileSync(path.join(root, 'first.ready'), 'utf8'));
        expect(() => process.kill(pid, 0)).toThrow();
    });
    it('fails and cleans up when a required command cannot start', async () => {
        expect(await launch('spawn')).toBe(1);
    });
});
