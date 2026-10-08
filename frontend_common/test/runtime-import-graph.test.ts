// @vitest-environment node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import ts from 'typescript';
import { runtimeClosure } from './runtime-import-graph.ts';

let root: string;
beforeEach(() => { root = fs.mkdtempSync(path.join(os.tmpdir(), 'speleodb-runtime-graph-')); });
afterEach(() => { fs.rmSync(root, { recursive: true, force: true }); });
function fixture(files: Record<string, string>) {
    for (const [file, source] of Object.entries(files)) {
        fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true });
        fs.writeFileSync(path.join(root, file), source);
    }
}

it('follows static, re-export, nested dynamic and worker edges through cycles', () => {
    fixture({
        'entry.ts': 'import "./static.ts"; export { value } from "./export.ts"; async function load() { return import("./dynamic.ts"); } new Worker(new URL("./worker.ts", import.meta.url), {type: "module"});',
        'static.ts': 'export const value = 1;',
        'export.ts': 'export * from "./static.ts";',
        'dynamic.ts': 'export const load = () => import(`./nested.ts`);',
        'nested.ts': 'import "./entry.ts";',
        'worker.ts': 'import "./worker-leaf.ts";',
        'worker-leaf.ts': 'export const value = 2;',
    });
    expect([...runtimeClosure('entry.ts', root)].map(file => path.basename(file)).sort()).toEqual([
        'dynamic.ts', 'entry.ts', 'export.ts', 'nested.ts', 'static.ts', 'worker-leaf.ts', 'worker.ts',
    ]);
});

it('omits erased declarations and import types while retaining inline type-only side effects', () => {
    const source = 'import type { A } from "./erased.ts"; export type { B } from "./erased.ts"; type C = import("./erased.ts").C; import { type D } from "./retained.ts"; export { type E } from "./retained.ts";';
    fixture({ 'entry.ts': source, 'retained.ts': '' });
    // Missing erased.ts also proves the walker does not attempt to read it.
    expect([...runtimeClosure('entry.ts', root)].map(file => path.basename(file))).toEqual(['entry.ts', 'retained.ts']);
    const emitted = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.Preserve, verbatimModuleSyntax: true } }).outputText;
    expect(emitted).not.toContain('erased.ts');
    expect(emitted).toContain('import {} from "./retained.ts"');
    expect(emitted).toContain('export {} from "./retained.ts"');
});

it('ignores external packages, JSON and ordinary URLs that do not load modules', () => {
    fixture({ 'entry.ts': 'import "external-package"; import data from "./data.json"; new URL("./not-a-module.ts", "https://example.test/");' });
    expect([...runtimeClosure('entry.ts', root)]).toEqual([path.join(root, 'entry.ts')]);
});

it.each([
    ['import(target)', 'Unclassified dynamic import'],
    ['new Worker(new URL(target, import.meta.url))', 'Unclassified module URL'],
    ['new Worker(workerUrl)', 'Unclassified worker URL'],
    ['new SharedWorker("./worker.ts")', 'Unclassified worker URL'],
    ['import.meta.glob("./*.ts")', 'Glob requires Vite asset-graph classification'],
])('fails closed on %s', (source, message) => {
    fixture({ 'entry.ts': source });
    expect(() => runtimeClosure('entry.ts', root)).toThrow(message);
});

it('traverses default source exports, legacy source conditions and package-internal JS specifiers', () => {
    fixture({
        'entry.ts': 'import "@speleodb/map-core"; import "@speleodb/map-viewer";',
        'node_modules/@speleodb/map-core/package.json': JSON.stringify({ exports: { '.': { 'speleodb-source': './src/index.ts', types: './dist/index.d.ts', import: './dist/index.js' } } }),
        'node_modules/@speleodb/map-core/src/index.ts': 'export * from "./leaf.js";',
        'node_modules/@speleodb/map-core/src/leaf.ts': 'export const value = 1;',
        'node_modules/@speleodb/map-viewer/package.json': JSON.stringify({ exports: { '.': { types: './src/index.ts', default: './src/index.ts' } } }),
        'node_modules/@speleodb/map-viewer/src/index.ts': 'export const value = 2;',
    });
    expect([...runtimeClosure('entry.ts', root)].map(file => path.relative(root, file))).toEqual([
        'entry.ts', 'node_modules/@speleodb/map-core/src/index.ts',
        'node_modules/@speleodb/map-core/src/leaf.ts', 'node_modules/@speleodb/map-viewer/src/index.ts',
    ]);
});

it('rejects shared declaration-only exports instead of auditing generated artifacts', () => {
    fixture({
        'entry.ts': 'import "@speleodb/map-core";',
        'node_modules/@speleodb/map-core/package.json': JSON.stringify({ exports: { '.': { types: './dist/index.d.ts', import: './dist/index.js' } } }),
        'node_modules/@speleodb/map-core/dist/index.d.ts': 'export declare const value: number;',
    });
    expect(() => runtimeClosure('entry.ts', root)).toThrow('First-party runtime import must resolve to source');
});
