import type { BunLock, PackageManifest, SetupBunStep, RailpackRecipe } from '../../ts-types/testing/vitest/toolchain.ts';
// @vitest-environment node

import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const ROOT = process.cwd();
const INSTALL_SCRIPT_NAMES = ['preinstall', 'install', 'postinstall'];
const read = (relativePath: string) => fs.readFileSync(path.join(ROOT, relativePath), 'utf8');
const packageJson = JSON.parse(read('package.json')) as PackageManifest;
const lock = JSON.parse(execFileSync('bun', [
    '--eval',
    'process.stdout.write(JSON.stringify(Bun.JSONC.parse(await Bun.stdin.text())))',
], { input: read('bun.lock'), encoding: 'utf8' })) as BunLock;

function setupSteps(value: unknown): SetupBunStep[] {
    if (!value || typeof value !== 'object') return [];
    const candidate = value as Partial<SetupBunStep>;
    const current = candidate.uses?.startsWith('oven-sh/setup-bun@') ? [value as SetupBunStep] : [];
    return [...current, ...Object.values(value).flatMap(setupSteps)];
}

function installedPackages(modulesDirectory: string): PackageManifest[] {
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

            const manifest = JSON.parse(fs.readFileSync(path.join(packageDirectory, 'package.json'), 'utf8')) as PackageManifest;
            return [manifest, ...installedPackages(path.join(packageDirectory, 'node_modules'))];
        });
}

describe('Bun package manager contract', () => {
    it('starts Django without building or watching frontend assets', () => {
        const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-manual-assets-'));
        try {
            const bin = path.join(directory, 'bin');
            const trace = path.join(directory, 'commands');
            fs.mkdirSync(bin);
            fs.writeFileSync(path.join(directory, 'bun.lock'), '{}\n');
            for (const command of ['bun', 'python']) {
                fs.writeFileSync(path.join(bin, command), `#!/bin/sh\nprintf '${command} %s\\n' "$*" >> "$SPELEO_TEST_TRACE"\n`, { mode: 0o755 });
            }
            const result = spawnSync('bash', [path.join(ROOT, 'compose/start')], {
                cwd: directory,
                env: { ...process.env, SPELEODB_LOCAL_PACKAGES: '0', PATH: `${bin}:${process.env.PATH}`, SPELEO_TEST_TRACE: trace },
                encoding: 'utf8', timeout: 5000,
            });
            expect(result.error).toBeUndefined();
            expect(result.status).toBe(0);
            expect(fs.readFileSync(trace, 'utf8').trim().split('\n')).toEqual([
                'python manage.py migrate',
                'bun scripts/check-shared-package-pins.ts',
                'bun install --frozen-lockfile',
                'python manage.py runserver_plus 0000:8000',
            ]);
        } finally {
            fs.rmSync(directory, { recursive: true, force: true });
        }
    });

    it.each([
        { failedStage: 'install', exitCode: 97, expectedCommands: ['bun install --frozen-lockfile'] },
        { failedStage: 'build', exitCode: 98, expectedCommands: ['bun install --frozen-lockfile', 'bun run build'] },
        { failedStage: '', exitCode: 0, expectedCommands: [
            'bun install --frozen-lockfile', 'bun run build',
            'python manage.py collectstatic --noinput', 'python manage.py compress --force',
        ] },
    ])('propagates post_compile status without publishing after $failedStage failure', ({ failedStage, exitCode, expectedCommands }) => {
        const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-post-compile-'));
        try {
            const bin = path.join(directory, 'bin');
            const trace = path.join(directory, 'commands');
            fs.mkdirSync(bin);
            fs.writeFileSync(path.join(directory, 'bun.lock'), '{}\n');
            fs.writeFileSync(path.join(bin, 'bun'), `#!/bin/sh
printf 'bun %s\\n' "$*" >> "$SPELEO_TEST_TRACE"
if [ "$1" = install ] && [ "$SPELEO_TEST_FAILED_STAGE" = install ]; then exit 97; fi
if [ "$1" = run ] && [ "$2" = build ] && [ "$SPELEO_TEST_FAILED_STAGE" = build ]; then exit 98; fi
exit 0
`, { mode: 0o755 });
            fs.writeFileSync(path.join(bin, 'python'), `#!/bin/sh
printf 'python %s\\n' "$*" >> "$SPELEO_TEST_TRACE"
exit 0
`, { mode: 0o755 });
            const result = spawnSync('bash', [path.join(ROOT, 'bin/post_compile')], {
                cwd: directory,
                env: {
                    ...process.env, PATH: `${bin}:${process.env.PATH}`,
                    SPELEO_TEST_TRACE: trace, SPELEO_TEST_FAILED_STAGE: failedStage,
                },
                encoding: 'utf8',
                timeout: 5000,
            });
            expect(result.error).toBeUndefined();
            expect(result.status).toBe(exitCode);
            expect(fs.readFileSync(trace, 'utf8').trim().split('\n')).toEqual(expectedCommands);
        } finally {
            fs.rmSync(directory, { recursive: true, force: true });
        }
    });

    it.each(['compose/start', 'bin/post_compile'])('rejects a missing lock before running Bun in %s', script => {
        const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-missing-lock-'));
        try {
            const bin = path.join(directory, 'bin');
            fs.mkdirSync(bin);
            fs.writeFileSync(path.join(bin, 'python'), '#!/bin/sh\nexit 0\n', { mode: 0o755 });
            fs.writeFileSync(path.join(bin, 'bun'), '#!/bin/sh\nexit 97\n', { mode: 0o755 });
            const result = spawnSync('bash', [path.join(ROOT, script)], {
                cwd: directory,
                env: { ...process.env, SPELEODB_LOCAL_PACKAGES: '0', PATH: `${bin}:${process.env.PATH}` },
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
        expect((Bun.TOML.parse(read('bunfig.toml')) as {run: {bun: boolean}}).run.bun).toBe(true);
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
        const recipe = JSON.parse(read('railpack.json')) as RailpackRecipe;
        expect(recipe.packages.bun).toBeUndefined();
        const commands = recipe.steps.build.commands.map(command => command.cmd);
        expect(commands).toContain('mise exec -- bun --version');
        expect(commands).toContain("sh -c 'test -s bun.lock && mise exec -- bun install --frozen-lockfile'");
        expect(commands).toContain('mise exec -- bun run build');
    });

    it('keeps every declared dependency and registry archive in the committed lockfile', () => {
        for (const group of ['dependencies', 'devDependencies', 'optionalDependencies'] as const) {
            expect(lock.workspaces[''][group] ?? {}).toEqual(packageJson[group] ?? {});
        }

        expect(packageJson.overrides?.['@speleodb/map-core']).toBe(packageJson.dependencies?.['@speleodb/map-core']);
        expect(lock.overrides).toEqual(packageJson.overrides);

        for (const [packagePath, lockedPackage] of Object.entries(lock.packages)) {
            // Bun can record the same Git dependency beneath another package.
            const packageName = ['@speleodb/map-core', '@speleodb/map-viewer'].find(name => (
                packagePath === name || packagePath.endsWith(`/${name}`)
            ));
            if (packageName) {
                // The manifest preserves the full immutable revision; Bun's
                // GitHub archive identity abbreviates it in the package tuple.
                const declaration = packageJson.dependencies?.[packageName];
                expect(declaration).toMatch(/^git\+https:\/\/github\.com\/[^/]+\/[^#]+#[a-f0-9]{40}$/);
                const repository = new URL(declaration!.replace(/^git\+/, ''));
                const archive = repository.pathname.slice(1).replace(/\.git$/, '');
                expect(lockedPackage[0], packagePath).toBe(`${packageName}@github:${archive}${repository.hash.slice(0, 8)}`);
                expect(lockedPackage[3]).toMatch(/^sha512-/);
                continue;
            }
            expect(lockedPackage[0], packagePath).toMatch(/@\d+\.\d+\.\d+/);
            if (!lockedPackage[2].bundled) {
                expect(lockedPackage[3], `Missing integrity for ${packagePath}`).toMatch(/^sha512-/);
            }
        }
    });

    it.each([
        { description: 'published immutable revisions', replacement: undefined, override: undefined, status: 0 },
        { description: 'local paths', replacement: 'file:./packages/map-core', override: undefined, status: 1 },
        { description: 'floating branches', replacement: 'git+https://github.com/OpenSpeleo/SpeleoDB-TS-MapCore.git#master', override: undefined, status: 1 },
        { description: 'abbreviated revisions', replacement: 'git+https://github.com/OpenSpeleo/SpeleoDB-TS-MapCore.git#6ce4262', override: undefined, status: 1 },
        { description: 'a mismatched core override', replacement: undefined, override: '^0.1.0', status: 1 },
    ])('checks shared-package release pins for $description', ({ replacement, override, status }) => {
        const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-package-pins-'));
        try {
            const dependencies = { ...packageJson.dependencies };
            if (replacement !== undefined) dependencies['@speleodb/map-core'] = replacement;
            fs.mkdirSync(path.join(directory, 'scripts'));
            const script = path.join(directory, 'scripts/check-shared-package-pins.ts');
            fs.writeFileSync(script, read('scripts/check-shared-package-pins.ts'));
            fs.writeFileSync(path.join(directory, 'package.json'), JSON.stringify({
                dependencies,
                overrides: { '@speleodb/map-core': override ?? dependencies['@speleodb/map-core'] },
            }));
            const result = spawnSync('bun', [script], {
                cwd: directory,
                encoding: 'utf8',
                timeout: 5000,
            });
            expect(result.error).toBeUndefined();
            expect(result.status).toBe(status);
            if (status === 0) expect(result.stderr).toBe('');
            else expect(result.stderr).toMatch(/full 40-character commit SHA|override must exactly match/);
        } finally {
            fs.rmSync(directory, { recursive: true, force: true });
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
