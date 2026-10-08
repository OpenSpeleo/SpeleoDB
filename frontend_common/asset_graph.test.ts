import type entries from './entries.json';
import type { RolldownOutput } from 'rolldown';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

import { build as viteBuild } from 'vite';

const ROOT = process.cwd();
const REGISTRY = JSON.parse(
    fs.readFileSync(path.join(ROOT, 'frontend_common/entries.json'), 'utf8'),
) as typeof entries;

function listFiles(directory: string): string[] {
    return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
        const filePath = path.join(directory, entry.name);
        return entry.isDirectory() ? listFiles(filePath) : [filePath];
    });
}

function relative(filePath: string) {
    return path.relative(ROOT, filePath).split(path.sep).join('/');
}

function authoredFiles(roots: string[], extensions: string[]) {
    return roots
        .flatMap(root => listFiles(path.join(ROOT, root)))
        .filter(filePath => extensions.includes(path.extname(filePath)))
        .filter(filePath => !/\.test\.(?:js|ts)$/.test(filePath))
        .filter(filePath => !filePath.includes(`${path.sep}vendors${path.sep}`))
        .filter(filePath => !filePath.includes(`${path.sep}dist${path.sep}`))
        .filter(filePath => !filePath.includes(`${path.sep}test${path.sep}`))
        .filter(filePath => !filePath.includes(`${path.sep}tests${path.sep}`));
}

describe('first-party Vite graph', () => {
    it('uses physical TypeScript extensions for first-party module specifiers', () => {
        const files = [
            ...['frontend_common', 'frontend_private/static/private/ts', 'frontend_public/static/ts',
                'frontend_errors/static/ts', 'ts-types', 'scripts', 'tests/browser', '.railway']
                .flatMap(root => listFiles(path.join(ROOT, root)))
                .filter(file => file.endsWith('.ts')),
            ...['vite', 'vitest', 'eslint', 'playwright'].map(name => path.join(ROOT, `${name}.config.ts`)),
        ];
        const failures: string[] = [];
        for (const file of files) {
            const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
            const visit = (node: ts.Node): void => {
                if (ts.isStringLiteralLike(node) && node.text.startsWith('.')) {
                    const parent = node.parent;
                    const isModule = (ts.isImportDeclaration(parent) && parent.moduleSpecifier === node)
                        || (ts.isExportDeclaration(parent) && parent.moduleSpecifier === node)
                        || (ts.isLiteralTypeNode(parent) && ts.isImportTypeNode(parent.parent))
                        || (ts.isCallExpression(parent) && parent.arguments[0] === node
                            && /^(?:import|vi\.(?:mock|doMock|unmock|doUnmock|importActual|importMock))$/.test(parent.expression.getText(source)));
                    if (isModule) {
                        const target = path.resolve(path.dirname(file), node.text);
                        if (!/\.(?:ts|json)$/.test(node.text) || !fs.existsSync(target)) {
                            failures.push(`${relative(file)}: ${node.text}`);
                        }
                    }
                }
                ts.forEachChild(node, visit);
            };
            visit(source);
        }
        expect(failures).toEqual([]);
    });

    it('retains all logical entries with physical typed script sources', () => {
        expect(Object.keys(REGISTRY.scripts)).toHaveLength(37);
        expect(Object.keys(REGISTRY.styles)).toHaveLength(54);
        for (const source of Object.values(REGISTRY.scripts)) {
            expect(source).toMatch(/\.ts$/);
            expect(source).not.toMatch(/\.test\.ts$/);
            expect(fs.existsSync(path.join(ROOT, source))).toBe(true);
        }
    });
    it.each(['production', 'development'])('bundles every browser source without reload polling in %s mode', async mode => {
        const workerModules = new Set<string>();
        const result = await viteBuild({
            configFile: path.join(ROOT, 'vite.config.ts'),
            mode,
            logLevel: 'silent',
            build: { write: false },
            worker: {
                plugins: () => [{
                    name: 'test-worker-module-coverage',
                    generateBundle(_options, bundle) {
                        for (const output of Object.values(bundle)) {
                            if (output.type === 'chunk') {
                                for (const moduleId of Object.keys(output.modules)) workerModules.add(moduleId);
                            }
                        }
                    },
                }],
            },
        });
        const outputResult = result as RolldownOutput | RolldownOutput[];
        const outputs = Array.isArray(outputResult)
            ? outputResult.flatMap(environment => environment.output)
            : outputResult.output;
        const bundledModules = new Set(
            outputs
                .filter(output => output.type === 'chunk')
                .flatMap(output => Object.keys(output.modules))
                .map(moduleId => path.resolve(moduleId.split('?')[0]!)),
        );
        for (const moduleId of workerModules) bundledModules.add(path.resolve(moduleId.split('?')[0]!));
        expect([...workerModules].some(moduleId => moduleId.endsWith('/map/geojson_worker.ts'))).toBe(true);
        expect(
            [...bundledModules]
                .filter(moduleId => /\.test\.(?:js|ts)$/.test(moduleId)
                    || /\/(?:frontend_common\/test|tests\/browser|scripts)\//.test(moduleId))
                .map(relative),
        ).toEqual([]);
        expect(outputs.map(output => output.fileName).filter(file => /\.ts$/.test(file))).toEqual([]);
        if (mode === 'production') {
            expect(outputs.map(output => output.fileName).filter(file => /\.map$/.test(file))).toEqual([]);
        }
        const authored = authoredFiles(
            [
                'frontend_common',
                'frontend_private/static/private/ts',
                'frontend_public/static/ts',
                'frontend_errors/static/ts',
            ],
            ['.ts'],
        );

        expect(
            authored.filter(filePath => !bundledModules.has(path.resolve(filePath))).map(relative),
        ).toEqual([]);
        expect(outputs.some(output => output.fileName.includes('assets/dev/'))).toBe(false);
        for (const output of outputs) {
            if (output.type !== 'chunk') continue;
            for (const marker of ['speleo_dev_reload_target', 'startDevelopmentReload', '__assets__/generation/', 'speleodbReload']) {
                expect(output.code, output.fileName).not.toContain(marker);
            }
        }
    });

    it('registers or imports every authored CSS source', () => {
        const reachable = new Set<string>();
        const visit = (relativePath: string): void => {
            const normalized = relativePath.split(path.sep).join('/');
            if (reachable.has(normalized)) return;
            reachable.add(normalized);
            const absolutePath = path.join(ROOT, normalized);
            const source = fs.readFileSync(absolutePath, 'utf8');
            for (const match of source.matchAll(/@import\s+['"]([^'"]+)['"]/g)) {
                const imported = match[1]!;
                if (!imported.startsWith('.')) continue;
                visit(relative(path.resolve(path.dirname(absolutePath), imported)));
            }
        };
        Object.values(REGISTRY.styles).forEach(visit);

        const authored = authoredFiles(
            [
                'frontend_common',
                'frontend_private/static/private/css',
                'frontend_public/static/css',
                'frontend_errors/static/css',
                'tailwind_css',
            ],
            ['.css'],
        ).map(relative);

        expect(authored.filter(filePath => !reachable.has(filePath))).toEqual([]);
    });
});
