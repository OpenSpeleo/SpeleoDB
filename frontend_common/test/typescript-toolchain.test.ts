import type { CompilerConfiguration, PackageManifest } from '../../ts-types/testing/vitest/toolchain.ts';
// @vitest-environment node

import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { ESLint } from 'eslint';
import ts from 'typescript';
import eslintConfig from '../../eslint.config.ts';

const ROOT = process.cwd();
const PROJECTS = ['runtime', 'worker', 'development'];
const CONFIG_FILES = ['tsconfig.json', 'tsconfig.worker.json', 'tsconfig.development.json'];
const readConfig = (name: string): CompilerConfiguration => JSON.parse(fs.readFileSync(path.join(ROOT, name), 'utf8')) as CompilerConfiguration;

describe('TypeScript toolchain boundaries', () => {
    it('selects the native checker independently of the compiler API alias', () => {
        const version = execFileSync(process.execPath, [
            './node_modules/@typescript/native/bin/tsc', '--version',
        ], { cwd: ROOT, encoding: 'utf8' }).trim();
        expect(version).toBe('Version 7.0.2');
        expect(ts.versionMajorMinor).toBe('6.0');
    });

    it('keeps exactly three strict no-emit configurations with isolated runtime and worker globals', () => {
        const base = readConfig('tsconfig.json').compilerOptions;
        expect(fs.readdirSync(ROOT).filter(name => /^tsconfig(?:\..+)?\.json$/.test(name)).sort()).toEqual([...CONFIG_FILES].sort());
        for (const flag of [
            'strict', 'noImplicitAny', 'strictNullChecks', 'useUnknownInCatchVariables',
            'noUncheckedIndexedAccess', 'exactOptionalPropertyTypes', 'verbatimModuleSyntax',
            'isolatedModules', 'erasableSyntaxOnly', 'resolveJsonModule',
            'allowImportingTsExtensions', 'forceConsistentCasingInFileNames', 'noEmit', 'composite',
        ] as const) expect(base[flag], flag).toBe(true);
        expect(base.allowJs).toBe(false);
        expect(base.skipLibCheck).toBe(false);
        const projects = CONFIG_FILES.map(readConfig);
        expect(new Set(projects.map(project => project.compilerOptions.tsBuildInfoFile)).size).toBe(PROJECTS.length);
        for (const project of projects) {
            expect(project.references).toBeUndefined();
            expect(project.compilerOptions.allowJs).not.toBe(true);
            expect(project.compilerOptions.noEmit).not.toBe(false);
        }
        expect(projects[0]!.compilerOptions.types).toEqual(['vite/client']);
        expect(projects[1]!.compilerOptions.types).toEqual([]);
        expect(projects[1]!.compilerOptions.lib).toEqual(['ES2023', 'WebWorker']);
        expect(projects[2]!.compilerOptions.types).toEqual(['bun', 'node', 'vitest/globals']);
        expect(projects[2]!.compilerOptions.lib).toEqual(['DOM', 'DOM.Iterable', 'ES2023']);
        expect(projects[2]!.include).toEqual(expect.arrayContaining([
            '.railway/railway.ts', 'vite.config.ts', 'vitest.config.ts', 'eslint.config.ts',
            'scripts/test-frontend-uploads.ts', 'playwright.config.ts',
            'tests/browser/**/*.ts', 'ts-types/testing/browser/**/*.ts', 'ts-types/testing/vitest/**/*.ts',
        ]));
        for (const project of projects.slice(1)) expect(project.extends).toBe('./tsconfig.json');
        const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8')) as PackageManifest;
        const leafScripts = Object.keys(manifest.scripts!).filter(name => name.startsWith('typecheck:') && name !== 'typecheck:watch');
        expect(leafScripts.sort()).toEqual(PROJECTS.map(project => `typecheck:${project}`).sort());
        const buildCommand = `bun ./node_modules/@typescript/native/bin/tsc --build ${CONFIG_FILES.join(' ')}`;
        expect(manifest.scripts!.typecheck).toBe(buildCommand);
        expect(manifest.scripts!['typecheck:watch']).toBe(`${buildCommand} --watch --preserveWatchOutput`);
        expect(manifest.scripts!['typecheck:runtime']).toBe('bun ./node_modules/@typescript/native/bin/tsc -p tsconfig.json');
    });

    it.each([
        { project: 'runtime', validSource: 'document.createElement("div"); void import.meta.env.DEV;', forbiddenGlobals: ['process', 'vi', 'Bun', 'DedicatedWorkerGlobalScope'], forbiddenWindowEvidence: true },
        { project: 'worker', validSource: 'self.postMessage("ready"); const scope: DedicatedWorkerGlobalScope = self as DedicatedWorkerGlobalScope; void scope;', forbiddenGlobals: ['window', 'document', 'process', 'vi', 'Bun'] },
        { project: 'development', validSource: 'document.createElement("div"); void process.versions; void Bun.version; vi.fn(); void window.__viewerEvidence; void import.meta.glob;', forbiddenGlobals: ['DedicatedWorkerGlobalScope'] },
    ])('rejects foreign ambient globals in the $project compiler environment', ({ project, validSource, forbiddenGlobals, forbiddenWindowEvidence }) => {
        const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-ambient-canary-'));
        try {
            fs.symlinkSync(path.join(ROOT, 'node_modules'), path.join(directory, 'node_modules'));
            const sourcePath = path.join(directory, 'canary.ts');
            const configPath = path.join(directory, 'tsconfig.json');
            fs.writeFileSync(configPath, JSON.stringify({
                extends: path.join(ROOT, project === 'runtime' ? 'tsconfig.json' : `tsconfig.${project}.json`),
                compilerOptions: {
                    rootDir: '/',
                    tsBuildInfoFile: path.join(directory, 'canary.tsbuildinfo'),
                },
                // Retain the actual project's imported closure. Testing an empty
                // include list would miss globals leaked through declarations.
                files: [sourcePath],
            }));
            const check = (source: string) => {
                fs.writeFileSync(sourcePath, `export {};\n${source}\n`);
                return spawnSync(process.execPath, [
                    path.join(ROOT, 'node_modules/@typescript/native/bin/tsc'), '-p', configPath,
                ], { cwd: ROOT, encoding: 'utf8', timeout: 60_000 });
            };
            const valid = check(validSource);
            expect(valid.error).toBeUndefined();
            expect(valid.status, valid.stdout + valid.stderr).toBe(0);
            const invalid = check([
                ...forbiddenGlobals.map(name => `void ${name};`),
                ...(forbiddenWindowEvidence ? ['void window.__viewerEvidence;'] : []),
            ].join('\n'));
            expect(invalid.error).toBeUndefined();
            expect(invalid.status, invalid.stdout + invalid.stderr).toBe(1);
            for (const name of forbiddenGlobals) {
                expect(invalid.stdout).toContain(`Cannot find name '${name}'`);
            }
            if (forbiddenWindowEvidence) {
                expect(invalid.stdout).toContain("Property '__viewerEvidence' does not exist");
            }
        } finally {
            fs.rmSync(directory, { recursive: true, force: true });
        }
    }, 120_000);

    it.each(PROJECTS)('accepts typed values and rejects unsafe JSON with the %s lint environment', async project => {
        const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-lint-canary-'));
        try {
            fs.symlinkSync(path.join(ROOT, 'node_modules'), path.join(directory, 'node_modules'));
            const validPath = path.join(directory, 'valid.ts');
            const invalidPath = path.join(directory, 'invalid.ts');
            const configPath = path.join(directory, 'tsconfig.json');
            fs.writeFileSync(validPath, 'const value: string = "safe"; void value;\n');
            fs.writeFileSync(invalidPath, 'const value: string = JSON.parse("null"); void value;\n');
            fs.writeFileSync(configPath, JSON.stringify({
                extends: path.join(ROOT, project === 'runtime' ? 'tsconfig.json' : `tsconfig.${project}.json`),
                compilerOptions: {
                    rootDir: directory,
                    tsBuildInfoFile: path.join(directory, 'canary.tsbuildinfo'),
                },
                // Exercise the real compiler options and lint rules on tiny
                // inputs. Full application closure belongs to the ambient
                // canaries above and the normal typecheck/lint commands.
                include: [],
                files: [validPath, invalidPath],
            }));
            const eslint = new ESLint({
                cwd: directory,
                overrideConfigFile: true,
                overrideConfig: [
                    ...eslintConfig,
                    { languageOptions: { parserOptions: { project: [configPath], tsconfigRootDir: directory } } },
                ],
            });
            const [valid, invalid] = await eslint.lintFiles([validPath, invalidPath]);
            expect(valid!.messages).toEqual([]);
            expect(invalid!.messages.map(message => message.ruleId)).toContain('@typescript-eslint/no-unsafe-assignment');
        } finally {
            fs.rmSync(directory, { recursive: true, force: true });
        }
    });
});
