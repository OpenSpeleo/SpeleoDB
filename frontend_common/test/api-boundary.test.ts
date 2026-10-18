import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { auditApi } from '../../scripts/audit-api.ts';

const roots: string[] = [];
afterEach(() => roots.splice(0).forEach(root => rmSync(root, { recursive: true, force: true })));

function audit(source: string) {
    const root = mkdtempSync(path.join(tmpdir(), 'speleodb-api-audit-'));
    roots.push(root);
    mkdirSync(path.join(root, 'frontend_common'));
    writeFileSync(path.join(root, 'frontend_common/example.ts'), source);
    return auditApi(root, ['frontend_common/example.ts']);
}

describe('first-party API boundary audit', () => {
    it.each([
        'fetch(url)',
        'globalThis["fetch"](url)',
        'const send = window.fetch; send(url)',
        'const { fetch: send } = window; send(url)',
        'const send = fetch.bind(window); send(url)',
        'let send; send = fetch; send(url)',
        'const transport = { send: fetch }; transport.send(url)',
        'const send = $.ajax; send({ url })',
        'const Request = XMLHttpRequest; new Request()',
        'import * as sdk from "@speleodb/api"; sdk.apiRequest(url)',
    ])('rejects custom transport and aliases: %s', source => {
        expect(audit(source).length).toBeGreaterThan(0);
    });

    it('rejects handwritten routes even when passed through another helper', () => {
        const findings = audit('call(Urls["api:v2:projects"]()); const endpoint = "/api/v2/projects/";');
        expect(findings.filter(finding => finding.rule === 'handwritten-api-url')).toHaveLength(2);
    });

    it('allows generated operations and generated download URL builders', () => {
        expect(audit('import { v2ProjectsList, getV2GpsTrackExportGpxUrl } from "@speleodb/api"; v2ProjectsList(options); link.href = getV2GpsTrackExportGpxUrl(id);')).toEqual([]);
    });

    it('does not treat comments or string contents as executable network calls', () => {
        expect(audit('// fetch(url)\nconst message = "fetch(url) is not an operation";')).toEqual([]);
    });
});
