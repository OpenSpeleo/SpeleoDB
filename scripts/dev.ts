import { spawn } from 'node:child_process';
import type { ChildProcess } from 'node:child_process';

interface DevelopmentCommand {
    name: string;
    command: string;
    args: string[];
}

/** A single lifecycle for required children and their descendant process groups. */
export async function supervise(commands: DevelopmentCommand[], graceMs = 3000): Promise<number> {
    if (!commands.length) throw new Error('At least one development command is required');
    const children: ChildProcess[] = [];
    const exits: Promise<void>[] = [];
    let finish!: (code: number) => void;
    let stopping = false;
    const finished = new Promise<number>(resolve => { finish = resolve; });
    function signalChildren(signal: NodeJS.Signals) {
        for (const child of children) {
            if (child.pid === undefined) continue;
            try { process.kill(-child.pid, signal); } catch (error) {
                if (!(error instanceof Error && 'code' in error && error.code === 'ESRCH')) throw error;
            }
        }
    }
    function stop(code: number, signal: NodeJS.Signals = 'SIGTERM') {
        if (stopping) return;
        stopping = true;
        signalChildren(signal);
        finish(code);
    }
    const interrupt = () => stop(130, 'SIGINT');
    const terminate = () => stop(143);
    process.on('SIGINT', interrupt);
    process.on('SIGTERM', terminate);
    try {
        for (const definition of commands) {
            const child = spawn(definition.command, definition.args, { stdio: 'inherit', detached: true });
            children.push(child);
            exits.push(new Promise(resolve => {
                child.once('error', error => {
                    console.error(`${definition.name} failed to start:`, error);
                    stop(1);
                    resolve();
                });
                child.once('exit', (code, signal) => {
                    if (!stopping) {
                        console.error(`${definition.name} exited unexpectedly (${signal ?? code}).`);
                        stop(code || 1);
                    }
                    resolve();
                });
            }));
        }
        const code = await finished;
        const escalation = setTimeout(() => signalChildren('SIGKILL'), graceMs);
        try {
            await Promise.all(exits);
            // A watcher can exit before its compiler descendants. Keep the grace
            // period alive until their groups exit too, then force any survivors.
            const deadline = Date.now() + graceMs;
            while (Date.now() < deadline && children.some(child => {
                if (child.pid === undefined) return false;
                try { process.kill(-child.pid, 0); return true; } catch { return false; }
            })) {
                await new Promise(resolve => setTimeout(resolve, 25));
            }
            signalChildren('SIGKILL');
        } finally { clearTimeout(escalation); }
        return code;
    } finally {
        process.off('SIGINT', interrupt);
        process.off('SIGTERM', terminate);
    }
}

if (import.meta.main) {
    const commands: DevelopmentCommand[] = [
        { name: 'Vite', command: process.execPath, args: ['./node_modules/.bin/vite', 'build', '--watch', '--mode', 'development'] },
        { name: 'TypeScript', command: process.execPath, args: ['run', 'typecheck:watch'] },
    ];
    if (process.argv.includes('--django')) {
        commands.push({ name: 'Django', command: 'python', args: ['manage.py', 'runserver_plus', '0000:8000'] });
    }
    process.exitCode = await supervise(commands);
}
