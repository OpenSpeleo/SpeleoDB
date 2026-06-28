import fs from 'node:fs';
import path from 'node:path';

import { build as viteBuild } from 'vite';

const ROOT = process.cwd();
const REGISTRY = JSON.parse(
    fs.readFileSync(path.join(ROOT, 'frontend_common/entries.json'), 'utf8'),
);

function listFiles(directory) {
    return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
        const filePath = path.join(directory, entry.name);
        return entry.isDirectory() ? listFiles(filePath) : [filePath];
    });
}

function relative(filePath) {
    return path.relative(ROOT, filePath).split(path.sep).join('/');
}

function authoredFiles(roots, extension) {
    return roots
        .flatMap(root => listFiles(path.join(ROOT, root)))
        .filter(filePath => path.extname(filePath) === extension)
        .filter(filePath => !filePath.endsWith('.test.js'))
        .filter(filePath => !filePath.includes(`${path.sep}vendors${path.sep}`))
        .filter(filePath => !filePath.includes(`${path.sep}dist${path.sep}`))
        .filter(filePath => !filePath.includes(`${path.sep}test${path.sep}`))
        .filter(filePath => !filePath.includes(`${path.sep}tests${path.sep}`));
}

describe('first-party Vite graph', () => {
    it('bundles every authored JavaScript source', async () => {
        const result = await viteBuild({
            configFile: path.join(ROOT, 'vite.config.mjs'),
            logLevel: 'silent',
            build: { write: false },
        });
        const outputs = Array.isArray(result)
            ? result.flatMap(environment => environment.output)
            : result.output;
        const bundledModules = new Set(
            outputs
                .filter(output => output.type === 'chunk')
                .flatMap(output => Object.keys(output.modules))
                .map(moduleId => path.resolve(moduleId.split('?')[0])),
        );
        const authored = authoredFiles(
            [
                'frontend_common',
                'frontend_private/static/private/js',
                'frontend_public/static/js',
                'frontend_errors/static/js',
            ],
            '.js',
        );

        expect(
            authored.filter(filePath => !bundledModules.has(path.resolve(filePath))).map(relative),
        ).toEqual([]);
    });

    it('registers or imports every authored CSS source', () => {
        const reachable = new Set();
        const visit = relativePath => {
            const normalized = relativePath.split(path.sep).join('/');
            if (reachable.has(normalized)) return;
            reachable.add(normalized);
            const absolutePath = path.join(ROOT, normalized);
            const source = fs.readFileSync(absolutePath, 'utf8');
            for (const match of source.matchAll(/@import\s+['"]([^'"]+)['"]/g)) {
                const imported = match[1];
                if (!imported.startsWith('.')) continue;
                visit(relative(path.resolve(path.dirname(absolutePath), imported)));
            }
        };
        Object.values(REGISTRY.styles).forEach(visit);

        const authored = authoredFiles(
            [
                'frontend_common',
                'frontend_private/static/private/css',
                'frontend_public/static/css',
                'frontend_errors/static/css',
                'tailwind_css',
            ],
            '.css',
        ).map(relative);

        expect(authored.filter(filePath => !reachable.has(filePath))).toEqual([]);
    });
});
