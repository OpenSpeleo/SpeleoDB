// @vitest-environment node

import { execFileSync, spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { auditJavaScript, auditOptions, VENDOR_FILES, workspaceFiles } from '../../scripts/audit-javascript.ts';
import { auditGeneratedHtml, auditHtml, auditTemplates } from '../../scripts/audit-templates.ts';

const ROOT = process.cwd();
const temporaryDirectories: string[] = [];
function fixture(files: Record<string, string>): string {
    const directory = mkdtempSync(path.join(os.tmpdir(), 'speleodb-source-audit-'));
    temporaryDirectories.push(directory);
    for (const [name, contents] of Object.entries(files)) {
        const file = path.join(directory, name);
        mkdirSync(path.dirname(file), { recursive: true });
        writeFileSync(file, contents);
    }
    return directory;
}

afterEach(() => {
    for (const directory of temporaryDirectories.splice(0)) rmSync(directory, { recursive: true, force: true });
});

describe('JavaScript ownership audit', () => {
    it('allows only the fifteen exact vendor identities', () => {
        expect(VENDOR_FILES.size).toBe(15);
        expect(auditJavaScript([...VENDOR_FILES])).toEqual([]);
        expect(auditJavaScript(['frontend_public/static/ts/vendors/application.js'])).toEqual([
            expect.objectContaining({ rule: 'authored-javascript' }),
        ]);
    });

    it('checks file ownership and extensions independently of module references', () => {
        expect(auditJavaScript(['app.ts', 'docs/JavaScript.md', 'ts-types/app.d.ts'])).toEqual([]);
        expect(auditJavaScript(['app.js', 'config.mjs', 'utility.cjs']).map(finding => finding.file))
            .toEqual(['app.js', 'config.mjs', 'utility.cjs']);
        expect(auditJavaScript(['app.js', 'app.ts']).map(finding => finding.rule))
            .toEqual(['authored-javascript', 'ambiguous-source']);
        expect(auditJavaScript([
            'frontend_public/static/ts/vendors/alpinejs.min.js',
            'frontend_public/static/ts/vendors/alpinejs.min.ts',
        ]).map(finding => finding.rule)).toEqual(['ambiguous-source']);
    });

    it('walks standalone mounts without Git and excludes only owned output/dependency paths', () => {
        const root = fixture({
            'app.js': '', 'node_modules/dependency/index.js': '', '.venv/dependency.js': '',
            'staticfiles/collected.js': '', 'speleodb/common/static/speleodb/vite/assets/app.js': '',
            'feature/dist/application.js': '', 'frontend_public/static/ts/vendors/new.js': '',
        });
        expect(workspaceFiles(root)).toEqual([
            'app.js', 'feature/dist/application.js', 'frontend_public/static/ts/vendors/new.js',
        ]);
    });

    it('includes tracked source even beneath generated and dependency exclusions', () => {
        const root = fixture({ 'staticfiles/hidden.js': '', 'node_modules/hidden.js': '' });
        execFileSync('git', ['init', '--quiet', root]);
        execFileSync('git', ['-C', root, 'add', '.']);
        const tracked = workspaceFiles(root, true);
        expect(tracked).toEqual(['node_modules/hidden.js', 'staticfiles/hidden.js']);
        expect(auditJavaScript(tracked)).toHaveLength(2);
    });

    it('does not count a deleted tracked source as a delivered working-tree file', () => {
        const root = fixture({ 'removed.js': '', 'staticfiles/retained.js': '' });
        execFileSync('git', ['init', '--quiet', root]);
        execFileSync('git', ['-C', root, 'add', '.']);
        rmSync(path.join(root, 'removed.js'));
        const tracked = workspaceFiles(root, true);
        expect(tracked).toEqual(['staticfiles/retained.js']);
        expect(auditJavaScript(tracked)).toHaveLength(1);
    });

    it('reports existing debt in inventory mode but fails enforcement', () => {
        const root = fixture({ 'app.js': '' });
        const script = path.join(ROOT, 'scripts/audit-javascript.ts');
        const inventory = spawnSync(process.execPath, [script, '--root', root, '--inventory'], { encoding: 'utf8' });
        expect(inventory.status, inventory.stderr).toBe(0);
        expect(inventory.stdout).toContain('authored-javascript');
        const enforced = spawnSync(process.execPath, [script, '--root', root], { encoding: 'utf8' });
        expect(enforced.status).toBe(1);
        expect(enforced.stdout).toContain('"mode": "enforce"');
    });

    it('rejects incomplete and unknown command arguments', () => {
        expect(() => auditOptions(['--root'])).toThrow('Unknown or incomplete');
        expect(() => auditOptions(['--root', '--inventory'])).toThrow('Unknown or incomplete');
        expect(() => auditOptions(['--skip'])).toThrow('Unknown or incomplete');
    });
});

describe('executable template and generated HTML audit', () => {
    it('accepts inert JSON, external vendors, comments, and inert data hooks', () => {
        const source = `<script type="application/json">{"example":"<img onerror='example'>"}</script>
            <script src="https://cdn.example/vendor.js"></script>
            <div data-controller="menu" x-cloak></div>
            {% comment %}<div onclick="example()">{% endcomment %}
            <!-- <script>example()</script> -->`;
        expect(auditHtml(source, 'page.html')).toEqual([]);
    });

    it('rejects module bodies and native, long-form Alpine and shorthand expressions', () => {
        const source = `<script type="module">initialize()</script>
            <div title="a > b" onclick="run()" x-data="{}" x-bind:class="active" @click.stop="run()" :class="active"></div>`;
        const findings = auditHtml(source, 'page.html');
        expect(findings.map(finding => finding.rule)).toEqual([
            'inline-script', ...Array<string>(5).fill('executable-attribute'),
        ]);
        expect(findings[1]?.line).toBe(2);
    });

    it('parses generated source literals and template substitutions without auditing comments', () => {
        const source = [
            '// <div onclick="commentOnly()"></div>',
            'const html = `<button title="${name}" @click="${action}">Open</button>`;',
            'const fragment = "onclick=\\\"run()\\\"";',
        ].join('\n');
        const findings = auditGeneratedHtml(source, 'controller.ts');
        expect(findings).toHaveLength(2);
        expect(findings.map(finding => finding.line)).toEqual([2, 3]);
    });

    it('does not interpret event names and CSS selectors as generated attributes', () => {
        expect(auditGeneratedHtml(`const names = ['once', 'onchange', ':checked', ':not([hidden])'];`, 'controller.ts')).toEqual([]);
    });

    it('checks runtime/vendor ownership while excluding test fixture examples', () => {
        const root = fixture({
            'frontend_common/controllers/menu.ts': 'const html = `<div x-show="open"></div>`;',
            'frontend_common/controllers/menu.test.ts': 'const html = `<div onclick="test()"></div>`;',
            'frontend_public/static/ts/vendors/alpinejs.min.js': 'const html = `<div x-data="{}"></div>`;',
            'frontend_public/static/ts/vendors/application.ts': 'const html = `<div x-init="run()"></div>`;',
            'frontend_private/templates/page.html': '<button onclick="run()">Open</button>',
        });
        expect(auditTemplates(root, workspaceFiles(root)).map(finding => finding.file)).toEqual([
            'frontend_common/controllers/menu.ts',
            'frontend_private/templates/page.html',
            'frontend_public/static/ts/vendors/application.ts',
        ]);
    });
});
