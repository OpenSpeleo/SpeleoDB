// @vitest-environment node

import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import ts from 'typescript';
import { workspaceFiles, VENDOR_FILES } from '../../scripts/audit-javascript.ts';

const ROOT = process.cwd();
const URL_DECLARATION = join(ROOT, 'ts-types/browser/urls.d.ts');
const declaration = ts.createSourceFile(URL_DECLARATION, readFileSync(URL_DECLARATION, 'utf8'), ts.ScriptTarget.Latest, true);
const contract = declaration.statements.find((statement): statement is ts.InterfaceDeclaration =>
    ts.isInterfaceDeclaration(statement) && statement.name.text === 'ApplicationUrls')!;
const routes = new Map(contract.members.map(member => {
    if (!ts.isMethodSignature(member) || !ts.isStringLiteral(member.name)) throw new Error('URL contracts must use finite named functions');
    return [member.name.text, member.parameters.filter(parameter => parameter.name.getText(declaration) !== 'this').length];
}));

it('matches every declared URL name and argument count to the backend route inventory', () => {
    const backend = JSON.parse(readFileSync(join(ROOT, 'speleodb/common/tests/url_config.json'), 'utf8')) as Array<{ name: string; url: string }>;
    const byName = new Map(backend.map(route => [route.name, route.url]));
    expect(routes.size).toBe(79);
    for (const [name, arity] of routes) {
        expect(byName.has(name), name).toBe(true);
        expect(byName.get(name)!.match(/<[^>]+>/g)?.length ?? 0, name).toBe(arity);
    }
});

it('covers literal URL lookups in every application module without parsing comments as calls', () => {
    const names = new Set<string>();
    for (const file of workspaceFiles(ROOT)) {
        if (!/^frontend_(?:common|public|private|errors)\//.test(file)
            || !/\.(?:js|ts)$/.test(file) || /\.test\./.test(file)
            || file.includes('/test/') || file.includes('/tests/') || VENDOR_FILES.has(file)) continue;
        const source = ts.createSourceFile(file, readFileSync(join(ROOT, file), 'utf8'), ts.ScriptTarget.Latest, true);
        const visit = (node: ts.Node): void => {
            if (ts.isElementAccessExpression(node)
                && /^(?:window\.)?Urls$/.test(node.expression.getText(source))
                && ts.isStringLiteral(node.argumentExpression)) names.add(node.argumentExpression.text);
            ts.forEachChild(node, visit);
        };
        visit(source);
    }
    expect(names.size).toBeGreaterThanOrEqual(60);
    expect([...names].filter(name => !routes.has(name))).toEqual([]);
});

it('rejects unknown route names, broad string lookup and incorrect argument tuples in the native checker', () => {
    const directory = mkdtempSync(join(tmpdir(), 'speleodb-url-contract-'));
    try {
        symlinkSync(join(ROOT, 'node_modules'), join(directory, 'node_modules'));
        const source = join(directory, 'contract.ts');
        const config = join(directory, 'tsconfig.json');
        writeFileSync(config, JSON.stringify({
            extends: join(ROOT, 'tsconfig.json'),
            compilerOptions: { tsBuildInfoFile: join(directory, 'contract.tsbuildinfo') },
            files: [source, URL_DECLARATION, join(ROOT, 'ts-types/domain/identifiers.ts')],
            include: [], exclude: [],
        }));
        const check = (text: string) => {
            writeFileSync(source, `export {};\n${text}\n`);
            return spawnSync(process.execPath, [join(ROOT, 'node_modules/@typescript/native/bin/tsc'), '-p', config], { cwd: ROOT, encoding: 'utf8' });
        };
        const valid = check("Urls['api:v2:projects'](); Urls['api:v2:experiment-records']('station', 'experiment'); Urls['private:project_details'](42);");
        expect(valid.status, valid.stdout + valid.stderr).toBe(0);
        for (const text of [
            "Urls['private:unknown']('id');",
            "declare const route: string; Urls[route]('id');",
            "Urls['api:v2:experiment-records']('station');",
            "Urls['api:v2:projects']('extra');",
        ]) {
            const invalid = check(text);
            expect(invalid.status, invalid.stdout + invalid.stderr).toBe(1);
        }
    } finally {
        rmSync(directory, { recursive: true, force: true });
    }
});
