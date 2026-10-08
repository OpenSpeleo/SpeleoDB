import { spawnSync } from 'node:child_process';

import './shared-map-packages.ts';

const projects = {
    runtime: 'tsconfig.json',
    worker: 'tsconfig.worker.json',
    development: 'tsconfig.development.json',
};
const scope = process.argv.find(argument => argument.startsWith('--scope='))?.slice('--scope='.length);
if (scope && !(scope in projects)) throw new Error(`Unknown TypeScript project: ${scope}`);
const selected = scope ? [[scope, projects[scope as keyof typeof projects]]] : Object.entries(projects);
const commands = selected.map(([name, project]) => ({
    name: `TypeScript ${name}`,
    command: process.execPath,
    args: ['./node_modules/@typescript/native/bin/tsc', '-p', project!],
}));
for (const command of commands) {
    const result = spawnSync(command.command, command.args, { stdio: 'inherit' });
    if (result.error) throw result.error;
    if (result.status !== 0) {
        process.exitCode = result.status ?? 1;
        break;
    }
}
