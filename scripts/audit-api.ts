import { readFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
import { workspaceFiles } from './audit-javascript.ts';
import type { AuditFinding } from './audit-javascript.ts';

const SOURCE_ROOTS = ['frontend_common/', 'frontend_private/static/private/ts/', 'frontend_public/static/ts/'];
const NETWORK_NAMES = new Set(['fetch', 'XMLHttpRequest', 'ajax', 'getJSON', 'getScript', 'axios', 'ky', 'superagent', 'apiRequest']);
const TRANSPORT_IMPORTS = new Set(['axios', 'ky', 'superagent', 'node-fetch', 'cross-fetch', 'undici']);

/** Each exception is a reviewed external, signed-storage, tile, or static-file boundary. */
export const NETWORK_EXCEPTIONS = [
    { file: 'frontend_common/controllers/feedback.ts', argument: 'context.endpoint', reason: 'External Formspree feedback form.' },
    { file: 'frontend_common/controllers/xls2compass.ts', argument: 'nominatim', reason: 'External Nominatim location search.' },
    { file: 'frontend_private/static/private/ts/map_viewer/components/context_menu.ts', argument: 'iconUrl', reason: 'Static SVG icon asset.' },
    { file: 'frontend_private/static/private/ts/map_viewer/map/layers/gps.ts', argument: 'record.file', reason: 'API-provided signed GPS-track object URL.' },
    { file: 'frontend_private/static/private/ts/map_viewer/map/layers/gis.ts', argument: 'record.file', reason: 'API-provided signed GIS-layer object URL.' },
    { file: 'frontend_private/static/private/ts/map_viewer/map/layers/survey.ts', argument: 'url', reason: 'API-provided signed project GeoJSON object URL.' },
    { file: 'frontend_private/static/private/ts/map_viewer/map/sources.ts', argument: 'tileUrl', reason: 'Renderer tile source URL.' },
] as const;

function propertyName(node: ts.Node): string | undefined {
    if (ts.isPropertyAccessExpression(node)) return node.name.text;
    if (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression)) return node.argumentExpression.text;
    return undefined;
}

/** Follow local aliases and destructuring with the checker, rather than matching call text. */
function networkReference(node: ts.Node, checker: ts.TypeChecker, seen = new Set<ts.Node>()): boolean {
    if (seen.has(node)) return false;
    seen.add(node);
    if (ts.isParenthesizedExpression(node) || ts.isAsExpression(node) || ts.isNonNullExpression(node)) return networkReference(node.expression, checker, seen);
    if (ts.isPropertyAccessExpression(node) || ts.isElementAccessExpression(node)) {
        const name = propertyName(node);
        if (name && NETWORK_NAMES.has(name)) return true;
        if (name === 'call' || name === 'apply' || name === 'bind') return networkReference(node.expression, checker, seen);
        if (name === 'get' || name === 'post') {
            return node.expression.getText() === '$' || node.expression.getText() === 'jQuery' || networkReference(node.expression, checker, seen);
        }
    }
    if (ts.isCallExpression(node) && propertyName(node.expression) === 'bind') return networkReference(node.expression, checker, seen);
    if (!ts.isIdentifier(node)) return false;
    if (NETWORK_NAMES.has(node.text)) return true;
    const symbol = checker.getSymbolAtLocation(node);
    return Boolean(symbol?.declarations?.some(declaration => {
        if (ts.isVariableDeclaration(declaration) && declaration.initializer) return networkReference(declaration.initializer, checker, seen);
        if (ts.isBindingElement(declaration)) {
            const name = declaration.propertyName ?? declaration.name;
            if (ts.isIdentifier(name) && NETWORK_NAMES.has(name.text)) return true;
        }
        if (ts.isImportSpecifier(declaration)) return NETWORK_NAMES.has((declaration.propertyName ?? declaration.name).text);
        return false;
    }));
}

function exceptionArgument(call: ts.CallExpression | ts.NewExpression, checker: ts.TypeChecker): string {
    const argument = call.arguments?.[0];
    if (argument && ts.isObjectLiteralExpression(argument)) {
        const url = argument.properties.find(property => ts.isPropertyAssignment(property) && property.name.getText() === 'url');
        if (url && ts.isPropertyAssignment(url)) {
            const declaration = checker.getSymbolAtLocation(url.initializer)?.valueDeclaration;
            const target = declaration && ts.isVariableDeclaration(declaration) ? declaration.initializer : url.initializer;
            if (target?.getText().includes('https://nominatim.openstreetmap.org/search?')) return 'nominatim';
        }
    }
    return argument?.getText() ?? '';
}

export function auditApi(root: string, files = workspaceFiles(root)): AuditFinding[] {
    const sources = files.filter(file => SOURCE_ROOTS.some(prefix => file.startsWith(prefix)) && file.endsWith('.ts') && !file.endsWith('.test.ts') && !file.includes('/test/') && !file.includes('/tests/'));
    const program = ts.createProgram(sources.map(file => path.join(root, file)), { noEmit: true, target: ts.ScriptTarget.ESNext, module: ts.ModuleKind.ESNext });
    const checker = program.getTypeChecker();
    const findings: AuditFinding[] = [];
    for (const file of sources) {
        const source = program.getSourceFile(path.join(root, file));
        if (!source) continue;
        const report = (node: ts.Node, rule: string, message: string) => findings.push({ file, rule, message, line: source.getLineAndCharacterOfPosition(node.getStart()).line + 1 });
        const visit = (node: ts.Node): void => {
            if ((ts.isCallExpression(node) || ts.isNewExpression(node)) && networkReference(node.expression, checker)) {
                const argument = exceptionArgument(node, checker);
                if (!NETWORK_EXCEPTIONS.some(exception => exception.file === file && exception.argument === argument)) {
                    report(node, 'custom-api-transport', 'Use a generated @speleodb/api operation. New external/storage boundaries require a reviewed exception.');
                }
            }
            if ((ts.isVariableDeclaration(node) || ts.isPropertyAssignment(node)) && node.initializer && networkReference(node.initializer, checker)) {
                report(node, 'transport-alias', 'Do not store raw network functions in application aliases; use generated operations.');
            }
            if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.EqualsToken && networkReference(node.right, checker)) {
                report(node, 'transport-alias', 'Do not assign raw network functions to application aliases.');
            }
            if (ts.isImportDeclaration(node) && ts.isStringLiteral(node.moduleSpecifier)) {
                const dependency = node.moduleSpecifier.text;
                if (TRANSPORT_IMPORTS.has(dependency)) report(node, 'transport-dependency', 'Application transports belong to @speleodb/api.');
                if (dependency === '@speleodb/api' && node.importClause?.namedBindings && ts.isNamedImports(node.importClause.namedBindings)) {
                    for (const imported of node.importClause.namedBindings.elements) {
                        const name = (imported.propertyName ?? imported.name).text;
                        if (name === 'apiRequest' || (name === 'createApiClient' && file !== 'frontend_common/api/client.ts')) {
                            report(imported, 'sdk-transport-boundary', 'Consumers use generated operations and the browser policy adapter.');
                        }
                    }
                }
            }
            if (ts.isStringLiteralLike(node) && (/^api:v\d:/.test(node.text) || /^\/(?:api\/v\d|_allauth)\//.test(node.text))) {
                report(node, 'handwritten-api-url', 'Use a generated operation or its generated URL builder.');
            }
            ts.forEachChild(node, visit);
        };
        visit(source);
    }
    return findings;
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
    const root = process.cwd();
    // Reading the manifest here also prevents silently auditing the wrong directory.
    JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
    const findings = auditApi(root);
    for (const finding of findings) console.error(`${finding.file}:${finding.line}: ${finding.rule}: ${finding.message}`);
    if (findings.length) process.exitCode = 1;
    else console.log('API boundaries pass: first-party requests use generated operations.');
}
