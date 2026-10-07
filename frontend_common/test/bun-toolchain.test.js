// @vitest-environment node

import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = process.cwd();
const INSTALL_SCRIPT_NAMES = ['preinstall', 'install', 'postinstall'];
const read = relativePath => fs.readFileSync(path.join(ROOT, relativePath), 'utf8');
const packageJson = JSON.parse(read('package.json'));
const lock = JSON.parse(execFileSync('bun', [
    '--eval',
    'process.stdout.write(JSON.stringify(Bun.JSONC.parse(await Bun.stdin.text())))',
], { input: read('bun.lock'), encoding: 'utf8' }));

function setupSteps(value) {
    if (!value || typeof value !== 'object') return [];
    const current = value.uses?.startsWith('oven-sh/setup-bun@') ? [value] : [];
    return [...current, ...Object.values(value).flatMap(setupSteps)];
}

function installedPackages(modulesDirectory) {
    if (!fs.existsSync(modulesDirectory)) {
        return [];
    }

    return fs.readdirSync(modulesDirectory, { withFileTypes: true })
        .filter(entry => entry.isDirectory() && !entry.name.startsWith('.'))
        .flatMap(entry => {
            const packageDirectory = path.join(modulesDirectory, entry.name);
            if (entry.name.startsWith('@')) {
                return installedPackages(packageDirectory);
            }

            const manifest = JSON.parse(fs.readFileSync(path.join(packageDirectory, 'package.json'), 'utf8'));
            return [manifest, ...installedPackages(path.join(packageDirectory, 'node_modules'))];
        });
}

describe('Bun package manager contract', () => {
    it.each(['compose/start', 'bin/post_compile'])('rejects a missing lock before running Bun in %s', script => {
        const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-missing-lock-'));
        try {
            const bin = path.join(directory, 'bin');
            fs.mkdirSync(bin);
            fs.writeFileSync(path.join(bin, 'python'), '#!/bin/sh\nexit 0\n', { mode: 0o755 });
            fs.writeFileSync(path.join(bin, 'bun'), '#!/bin/sh\nexit 97\n', { mode: 0o755 });
            const result = spawnSync('bash', [path.join(ROOT, script)], {
                cwd: directory,
                env: { ...process.env, PATH: `${bin}:${process.env.PATH}` },
                encoding: 'utf8',
                timeout: 5000,
            });
            expect(result.error).toBeUndefined();
            expect(result.status).toBe(1);
        } finally {
            fs.rmSync(directory, { recursive: true, force: true });
        }
    });

    it('runs the locked toolchain under the declared Bun runtime', () => {
        const bunVersion = read('.bun-version').trim();

        expect(bunVersion).toMatch(/^\d+\.\d+\.\d+$/);
        expect(packageJson.packageManager).toBe(`bun@${bunVersion}`);
        expect(execFileSync('bun', ['--version'], { encoding: 'utf8' }).trim()).toBe(bunVersion);
        expect(packageJson.engines.bun).toBe(bunVersion);
        expect(process.versions.bun).toBe(bunVersion);
        expect(Bun.TOML.parse(read('bunfig.toml')).run.bun).toBe(true);
    });

    it('uses the shared runtime version in workflow and image provisioning', () => {
        const workflows = fs.readdirSync(path.join(ROOT, '.github/workflows'))
            .filter(file => /\.ya?ml$/.test(file))
            .flatMap(file => setupSteps(Bun.YAML.parse(read(`.github/workflows/${file}`))));
        expect(workflows.length).toBeGreaterThan(0);
        for (const step of workflows) {
            expect(step.with['bun-version-file']).toBe('.bun-version');
            expect(step.with['bun-version']).toBeUndefined();
        }
        const dockerfile = read('compose/Dockerfile');
        expect(dockerfile).toContain('COPY .bun-version /tmp/.bun-version');
        expect(dockerfile).toContain('< /tmp/.bun-version');
        expect(dockerfile).toContain('bun-v${BUN_VERSION}');
        expect(dockerfile).toContain('test "$(bun --version)" = "${BUN_VERSION}"');
        const recipe = JSON.parse(read('railpack.json'));
        expect(recipe.packages.bun).toBeUndefined();
        const commands = recipe.steps.build.commands.map(command => command.cmd);
        expect(commands).toContain('mise exec -- bun --version');
        expect(commands).toContain("sh -c 'test -s bun.lock && mise exec -- bun install --frozen-lockfile'");
        expect(commands).toContain('mise exec -- bun run build');
    });

    it('keeps every declared dependency and registry archive in the committed lockfile', () => {
        for (const group of ['dependencies', 'devDependencies', 'optionalDependencies']) {
            expect(lock.workspaces[''][group] ?? {}).toEqual(packageJson[group] ?? {});
        }

        for (const [packagePath, lockedPackage] of Object.entries(lock.packages)) {
            expect(lockedPackage[0], packagePath).toMatch(/@\d+\.\d+\.\d+/);
            if (!lockedPackage[2].bundled) {
                expect(lockedPackage[3], `Missing integrity for ${packagePath}`).toMatch(/^sha512-/);
            }
        }
    });

    it('explicitly authorizes only the existing native installation scripts', () => {
        const trusted = packageJson.trustedDependencies;

        expect(trusted).toEqual(['esbuild', 'fsevents']);
        expect([...lock.trustedDependencies].sort()).toEqual([...trusted].sort());
        for (const packageName of trusted) {
            expect(lock.packages[packageName]).toBeDefined();
        }

        const installed = installedPackages(path.join(ROOT, 'node_modules'));
        expect(installed.some(manifest => manifest.name === 'esbuild')).toBe(true);
        for (const manifest of installed) {
            if (INSTALL_SCRIPT_NAMES.some(script => manifest.scripts?.[script])) {
                expect(trusted, `Unreviewed installation script in ${manifest.name}`).toContain(manifest.name);
            }
        }
    });
});
