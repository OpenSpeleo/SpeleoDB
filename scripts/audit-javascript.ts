import { execFileSync } from 'node:child_process';
import { existsSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export const VENDOR_FILES = new Set([
    'frontend_private/static/private/ts/vendors/Sortable.min.js',
    'frontend_private/static/private/ts/vendors/ag-grid-community.min.js',
    'frontend_private/static/private/ts/vendors/chart.js',
    'frontend_private/static/private/ts/vendors/chartjs-adapter-moment.js',
    'frontend_private/static/private/ts/vendors/flatpickr.js',
    'frontend_private/static/private/ts/vendors/moment.js',
    'frontend_private/static/private/ts/vendors/prism-bash.min.js',
    'frontend_private/static/private/ts/vendors/prism-json.min.js',
    'frontend_private/static/private/ts/vendors/prism-line-numbers.min.js',
    'frontend_private/static/private/ts/vendors/prism-makefile.min.js',
    'frontend_private/static/private/ts/vendors/prism.min.js',
    'frontend_public/static/ts/vendors/alpinejs.min.js',
    'frontend_public/static/ts/vendors/aos.js',
    'frontend_public/static/ts/vendors/jquery-3.7.1.js',
    'frontend_public/static/ts/vendors/swiper-bundle.min.js',
]);

const EXCLUDED_DIRECTORIES = new Set([
    '.git', '.venv', 'venv', 'node_modules', '.cache', '.artifacts',
    '.pytest_cache', '.mypy_cache', '__pycache__',
]);
const GENERATED_DIRECTORIES = new Set([
    'staticfiles',
    'speleodb/common/static/speleodb/vite',
    'frontend_private/static/private/ts/dist',
    'frontend_public/static/ts/dist',
]);

export interface AuditFinding {
    file: string;
    rule: string;
    message: string;
    line?: number;
}

export interface AuditOptions {
    root: string;
    inventory: boolean;
    tracked: boolean;
}

/** The default audit works in the standalone container without Git metadata. */
export function workspaceFiles(root: string, tracked = false): string[] {
    if (tracked) {
        // Tracked files bypass generated/dependency exclusions: source cannot
        // disappear from CI's audit by being committed beneath an output path.
        // Deleted tracked paths are absent from the working tree being checked.
        return execFileSync('git', ['-C', root, 'ls-files', '-z', '--cached'], {
            encoding: 'utf8',
        }).split('\0').filter(file => file && existsSync(path.join(root, file))).sort();
    }
    const visit = (relativeDirectory: string): string[] => readdirSync(
        path.join(root, relativeDirectory), { withFileTypes: true },
    ).flatMap(entry => {
        const relativePath = path.posix.join(relativeDirectory, entry.name);
        if (entry.isDirectory()) {
            if (EXCLUDED_DIRECTORIES.has(entry.name) || GENERATED_DIRECTORIES.has(relativePath)) return [];
            return visit(relativePath);
        }
        return entry.isFile() || entry.isSymbolicLink() ? [relativePath] : [];
    });
    return visit('').sort();
}

export function auditJavaScript(files: readonly string[]): AuditFinding[] {
    const paths = new Set(files);
    return files.flatMap(file => {
        if (!/\.(?:js|mjs|cjs)$/i.test(file)) return [];
        const findings: AuditFinding[] = VENDOR_FILES.has(file) ? [] : [{
            file, rule: 'authored-javascript', message: 'First-party JavaScript must be translated to TypeScript or explicitly removed.',
        }];
        const stem = file.replace(/\.(?:js|mjs|cjs)$/i, '');
        if (['.ts', '.mts', '.cts'].some(extension => paths.has(stem + extension))) {
            findings.push({ file, rule: 'ambiguous-source', message: 'JavaScript and TypeScript share a source stem.' });
        }
        return findings;
    });
}

export function auditOptions(args: readonly string[]): AuditOptions {
    const options = { root: process.cwd(), inventory: false, tracked: false };
    for (let index = 0; index < args.length; index += 1) {
        const argument = args[index];
        if (argument === '--inventory') options.inventory = true;
        else if (argument === '--tracked') options.tracked = true;
        else if (argument === '--root') {
            const directory = args[index + 1];
            if (directory === undefined || directory.startsWith('--')) throw new Error('Unknown or incomplete audit argument: --root');
            options.root = path.resolve(directory);
            index += 1;
        }
        else throw new Error(`Unknown or incomplete audit argument: ${argument ?? ''}`);
    }
    return options;
}

export function reportAudit(findings: readonly AuditFinding[], inventory: boolean): void {
    process.stdout.write(`${JSON.stringify({ mode: inventory ? 'inventory' : 'enforce', findings }, null, 2)}\n`);
    if (!inventory && findings.length > 0) process.exitCode = 1;
}

export function invokedDirectly(moduleUrl: string): boolean {
    const entry = process.argv[1];
    return entry !== undefined && moduleUrl === pathToFileURL(path.resolve(entry)).href;
}

if (invokedDirectly(import.meta.url)) {
    const options = auditOptions(process.argv.slice(2));
    reportAudit(auditJavaScript(workspaceFiles(options.root, options.tracked)), options.inventory);
}
