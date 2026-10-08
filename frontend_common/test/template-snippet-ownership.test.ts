interface TemplateReference { kind: string; expression: string; template: string | null; assignments: string[] }
// @vitest-environment node

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import path from 'node:path';

const ROOT = process.cwd();
const TEMPLATE_ROOTS = [
    'frontend_private/templates',
    'frontend_public/templates',
    'frontend_errors/templates',
    'speleodb/templates',
];
const DEAD_SNIPPETS = [
    'snippets/ajax_error_modal_management.js',
    'snippets/cylinder_modal_helpers.js',
    'snippets/sensor_modal_helpers.js',
];

function filesBelow(directory: string): string[] {
    return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
        const filename = path.join(directory, entry.name);
        return entry.isDirectory() ? filesBelow(filename) : [filename];
    });
}

// Fail closed on computed template names. A substring search misses names
// assembled with filters or aliases; retaining their enclosing assignments in
// the report makes any newly introduced dynamic include require source review.
function templateReferences(source: string): TemplateReference[] {
    const references: TemplateReference[] = [];
    const scopes: string[] = [];
    const activeSource = source
        .replace(/{%\s*comment\b[^%]*%}[\s\S]*?{%\s*endcomment\s*%}/g, '')
        .replace(/{#[\s\S]*?#}/g, '');
    for (const match of activeSource.matchAll(/{%\s*([\s\S]*?)\s*%}/g)) {
        const tag = match[1]!;
        if (/^with\s/.test(tag)) {
            scopes.push(tag.slice('with'.length).trim());
        } else if (tag === 'endwith') {
            scopes.pop();
        } else if (/^(include|extends)\s/.test(tag)) {
            const [, kind, expression] = tag.match(/^(include|extends)\s+([\s\S]*)$/)!;
            const literal = expression!.match(/^(['"])(.*?)\1(?=\s|$)/);
            references.push({
                kind: kind!,
                expression: expression!,
                template: literal ? literal[2]! : null,
                assignments: [...scopes],
            });
        }
    }
    return references;
}

const references = TEMPLATE_ROOTS.flatMap(root => {
    const directory = path.join(ROOT, root);
    return filesBelow(directory).flatMap(filename => templateReferences(readFileSync(filename, 'utf8'))
        .map(reference => ({ ...reference, file: path.relative(directory, filename), root })));
});

describe('unreachable executable template snippets', () => {
    it('keeps proven-unreachable executable snippets absent', () => {
        for (const snippet of DEAD_SNIPPETS) expect(existsSync(path.join(ROOT, 'frontend_private/templates', snippet))).toBe(false);
    });
    it('finds direct include targets without confusing include context assignments with the target', () => {
        expect(templateReferences('{% include "snippets/cylinder_modal_helpers.js" with kind="sensor" only %}'))
            .toEqual([{
                kind: 'include',
                expression: '"snippets/cylinder_modal_helpers.js" with kind="sensor" only',
                template: DEAD_SNIPPETS[1],
                assignments: [],
            }]);
    });

    it.each([
        '{% with fragment="snippets/"|add:kind|add:"_modal_helpers.js" %}{% include fragment %}{% endwith %}',
        '{% with "snippets/cylinder_modal_helpers.js" as fragment %}{% include fragment %}{% endwith %}',
        '{% with fragment="snippets/sensor_modal_helpers.js" %}{% with alias=fragment %}{% include alias %}{% endwith %}{% endwith %}',
    ])('exposes dynamic inclusion and its assignments: %s', source => {
        const [reference] = templateReferences(source);
        expect(reference!.kind).toBe('include');
        expect(reference!.template).toBeNull();
        expect(reference!.assignments.length).toBeGreaterThan(0);
        expect(reference!.assignments[0]).toContain('snippets/');
    });

    it('does not mistake quoted names followed by filters for static targets', () => {
        const [reference] = templateReferences('{% include "snippets/"|add:fragment %}');
        expect(reference!.template).toBeNull();
    });

    it('has no unresolved dynamic include that could select the obsolete fragments', () => {
        const includes = references.filter(reference => reference.kind === 'include');
        expect(includes.length).toBeGreaterThan(0);
        expect(includes.filter(reference => reference.template === null)).toEqual([]);
    });

    it('has no direct include or inheritance edge to an obsolete fragment', () => {
        const incoming = references.filter(reference => {
            if (reference.template === null) return false;
            const target = reference.template.startsWith('.')
                ? path.posix.join(path.posix.dirname(reference.file), reference.template)
                : path.posix.normalize(reference.template);
            return DEAD_SNIPPETS.includes(target);
        });
        expect(incoming).toEqual([]);
    });

    it('limits dynamic inheritance to the reviewed entity settings context', () => {
        const dynamic = references.filter(reference => reference.kind === 'extends' && reference.template === null);
        expect(dynamic).toHaveLength(3);
        for (const reference of dynamic) {
            expect(reference.expression).toBe('entity_settings_base_template|default:"pages/shared/entity_settings/base.html"');
            expect(reference.assignments).toEqual([]);
        }
        const providers = filesBelow(path.join(ROOT, 'frontend_private/views'))
            .filter(filename => filename.endsWith('.py'))
            .flatMap(filename => [...readFileSync(filename, 'utf8').matchAll(/\bentity_settings_base_template\s*=\s*([^\n]+)/g)]);
        expect(providers.length).toBeGreaterThan(0);
        for (const provider of providers) {
            expect(provider[1]).toMatch(/^"pages\/[a-z_]+\/base\.html",?\s*$/);
        }
    });
});
