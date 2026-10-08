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
    for (const [file, source] of Object.entries(files)) fs.writeFileSync(path.join(root, file), source);
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
