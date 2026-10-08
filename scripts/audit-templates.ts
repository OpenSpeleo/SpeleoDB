import { readFileSync } from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import {
    auditOptions, invokedDirectly, reportAudit, VENDOR_FILES, workspaceFiles,
} from './audit-javascript.ts';
import type { AuditFinding } from './audit-javascript.ts';

const INERT_SCRIPT_TYPES = new Set(['application/json', 'application/ld+json']);
const EXECUTABLE_ALPINE = /^(?:x-(?:data|init|show|text|html|model|bind|on|effect|for|if|id)(?:[.:]|$)|[@:])/i;
const ATTRIBUTE = /([^\s=/'"<>]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s<>]+)))?/g;
const OPEN_TAG = /<([a-z][\w:-]*)\b((?:[^'"<>]|"[^"]*"|'[^']*')*)>/gi;

function hideComments(source: string): string {
    return source.replace(/{%\s*comment\b[^%]*%}[\s\S]*?{%\s*endcomment\s*%}|{#[\s\S]*?#}|<!--[\s\S]*?-->/g,
        comment => comment.replace(/[^\n]/g, ' '));
}

/** Scan HTML tokens, preserving quoted > characters and original line offsets. */
export function auditHtml(source: string, file: string, baseLine = 1): AuditFinding[] {
    const active = hideComments(source);
    const findings: AuditFinding[] = [];
    let scriptBodyEnd = 0;
    for (const tag of active.matchAll(OPEN_TAG)) {
        if (tag.index < scriptBodyEnd) continue;
        const name = tag[1]?.toLowerCase();
        const attributes = tag[2] ?? '';
        const line = baseLine + active.slice(0, tag.index).split('\n').length - 1;
        let scriptType = '';
        let external = false;
        for (const attribute of attributes.matchAll(ATTRIBUTE)) {
            const attributeName = attribute[1] ?? '';
            const value = attribute[2] ?? attribute[3] ?? attribute[4] ?? '';
            if (attributeName.toLowerCase() === 'type') scriptType = value.toLowerCase();
            if (attributeName.toLowerCase() === 'src') external = true;
            if (/^on[a-z]+$/i.test(attributeName) || EXECUTABLE_ALPINE.test(attributeName)) {
                findings.push({ file, line, rule: 'executable-attribute', message: `Move ${attributeName} behavior to compiled TypeScript.` });
            }
        }
        if (name === 'script') {
            const bodyStart = tag.index + tag[0].length;
            const bodyEnd = active.toLowerCase().indexOf('</script', bodyStart);
            const body = active.slice(bodyStart, bodyEnd === -1 ? undefined : bodyEnd);
            scriptBodyEnd = bodyEnd === -1 ? active.length : bodyEnd;
            if (!external && !INERT_SCRIPT_TYPES.has(scriptType) && body.trim()) {
                findings.push({ file, line, rule: 'inline-script', message: 'Move executable script bodies to compiled TypeScript.' });
            }
        }
    }
    return findings;
}

/** Parse authored source so comments and escaped string delimiters are handled. */
export function auditGeneratedHtml(source: string, file: string): AuditFinding[] {
    const parsed = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS);
    const findings: AuditFinding[] = [];
    const inspect = (node: ts.Node): void => {
        if (ts.isStringLiteralLike(node) || ts.isTemplateExpression(node)) {
            const text = ts.isTemplateExpression(node)
                ? node.head.text + node.templateSpans.map(span => `__SPELEO_DYNAMIC__${span.literal.text}`).join('')
                : node.text;
            const line = parsed.getLineAndCharacterOfPosition(node.getStart(parsed)).line + 1;
            if (text.includes('<')) {
                findings.push(...auditHtml(text, file, line));
            } else if (/(?:^|\s)(?:on[a-z]+|x-[\w:.-]+|[@:][\w:.-]+)\s*=/i.test(text)) {
                findings.push(...auditHtml(`<audit ${text}>`, file, line));
            }
        }
        ts.forEachChild(node, inspect);
    };
    inspect(parsed);
    return findings;
}

export function auditTemplates(root: string, files: readonly string[]): AuditFinding[] {
    return files.flatMap(file => {
        if (VENDOR_FILES.has(file)) return [];
        const template = file.includes('/templates/') && /\.(?:html|js)$/.test(file);
        const runtime = /^(?:frontend_common|frontend_private\/static\/private\/ts|frontend_public\/static\/ts|frontend_errors\/static\/ts)\//.test(file)
            && /\.(?:js|mjs|cjs|ts)$/.test(file)
            && !/(?:\.test\.[^.]+$|\/tests?\/|\.d\.ts$)/.test(file);
        if (!template && !runtime) return [];
        const source = readFileSync(path.join(root, file), 'utf8');
        return template ? auditHtml(source, file) : auditGeneratedHtml(source, file);
    });
}

if (invokedDirectly(import.meta.url)) {
    const options = auditOptions(process.argv.slice(2));
    reportAudit(auditTemplates(options.root, workspaceFiles(options.root, options.tracked)), options.inventory);
}
