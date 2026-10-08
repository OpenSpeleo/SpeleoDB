import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

/** Test-only runtime closure; Vite asset tests separately own registry/glob expansion. */
export function runtimeClosure(entry: string, root = process.cwd()): Set<string> {
    const visited = new Set<string>();
    function follow(file: string): void {
        if (visited.has(file)) return;
        visited.add(file);
        const source = ts.createSourceFile(file, fs.readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true);
        function dependency(specifier: string): void {
            if (specifier.startsWith('.') && specifier.endsWith('.ts')) {
                follow(path.resolve(path.dirname(file), specifier));
            }
        }
        function visit(node: ts.Node): void {
            // Inline `type` specifiers retain an empty runtime import/export under
            // verbatimModuleSyntax. Only declaration-level `type` is erased.
            if (ts.isImportDeclaration(node) && !node.importClause?.isTypeOnly && ts.isStringLiteral(node.moduleSpecifier)) {
                dependency(node.moduleSpecifier.text);
            } else if (ts.isExportDeclaration(node) && !node.isTypeOnly && node.moduleSpecifier && ts.isStringLiteral(node.moduleSpecifier)) {
                dependency(node.moduleSpecifier.text);
            } else if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
                const specifier = node.arguments[0];
                if (!specifier || !ts.isStringLiteralLike(specifier)) throw new Error(`Unclassified dynamic import in ${file}`);
                dependency(specifier.text);
            } else if (ts.isNewExpression(node) && node.expression.getText(source) === 'URL'
                && node.arguments?.[1]?.getText(source) === 'import.meta.url') {
                const specifier = node.arguments[0];
                if (!specifier || !ts.isStringLiteralLike(specifier)) throw new Error(`Unclassified module URL in ${file}`);
                dependency(specifier.text);
            } else if (ts.isNewExpression(node)
                && /^(?:(?:window|globalThis|self)\.)?(?:Worker|SharedWorker)$/.test(node.expression.getText(source))) {
                const workerUrl = node.arguments?.[0];
                if (!workerUrl || !ts.isNewExpression(workerUrl) || workerUrl.expression.getText(source) !== 'URL'
                    || workerUrl.arguments?.[1]?.getText(source) !== 'import.meta.url') {
                    throw new Error(`Unclassified worker URL in ${file}`);
                }
            } else if (ts.isCallExpression(node) && node.expression.getText(source) === 'import.meta.glob') {
                throw new Error(`Glob requires Vite asset-graph classification in ${file}`);
            }
            ts.forEachChild(node, visit);
        }
        visit(source);
    }
    follow(path.resolve(root, entry));
    return visited;
}
