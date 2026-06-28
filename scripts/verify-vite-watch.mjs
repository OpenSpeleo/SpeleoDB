import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import {
    cp,
    mkdir,
    mkdtemp,
    readFile,
    rm,
    symlink,
    writeFile,
} from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const repositoryRoot = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    '..',
);
const mirrorRoot = await mkdtemp(path.join(tmpdir(), 'speleodb-vite-watch-'));
const outputRoot = path.join(
    mirrorRoot,
    'speleodb/common/static/speleodb/vite',
);
const manifestPath = path.join(outputRoot, '.vite/manifest.json');

const delay = (milliseconds) =>
    new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitFor(assertion, label, timeout = 20_000) {
    const deadline = Date.now() + timeout;
    let lastError;
    while (Date.now() < deadline) {
        try {
            return await assertion();
        } catch (error) {
            lastError = error;
            await delay(100);
        }
    }
    throw new Error(`Timed out waiting for ${label}`, { cause: lastError });
}

async function copy(relativePath) {
    const destination = path.join(mirrorRoot, relativePath);
    await mkdir(path.dirname(destination), { recursive: true });
    await cp(
        path.join(repositoryRoot, relativePath),
        destination,
        { recursive: true },
    );
}

async function manifestEntry(logicalName) {
    const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
    const matches = Object.values(manifest).filter(
        (entry) => entry.isEntry && entry.name === logicalName,
    );
    if (matches.length !== 1) {
        throw new Error(`Expected one manifest entry for ${logicalName}`);
    }
    return path.join(outputRoot, matches[0].file);
}

async function output(logicalName) {
    return readFile(await manifestEntry(logicalName), 'utf8');
}

async function outputGraph(logicalName) {
    const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
    const match = Object.entries(manifest).find(
        ([, entry]) => entry.isEntry && entry.name === logicalName,
    );
    if (!match) throw new Error(`Missing manifest entry for ${logicalName}`);
    const values = [];
    const visited = new Set();
    async function visit([key, entry]) {
        if (visited.has(key)) return;
        visited.add(key);
        for (const importedKey of entry.imports ?? []) {
            const imported = manifest[importedKey];
            if (!imported) throw new Error(`Missing manifest import ${importedKey}`);
            await visit([importedKey, imported]);
        }
        values.push(await readFile(path.join(outputRoot, entry.file), 'utf8'));
    }
    await visit(match);
    return values.join('\n');
}

function digest(value) {
    return createHash('sha256').update(value).digest('hex');
}

async function mutate(relativePath, transform) {
    const absolutePath = path.join(mirrorRoot, relativePath);
    const original = await readFile(absolutePath, 'utf8');
    await writeFile(absolutePath, transform(original));
    return async () => writeFile(absolutePath, original);
}

let watcher;
let watcherLog = '';
try {
    await Promise.all(
        [
            'vite.config.mjs',
            'package.json',
            'frontend_common',
            'frontend_errors',
            'frontend_private',
            'frontend_public',
            'tailwind_css',
            'speleodb/surveys/templatetags/project_types.py',
        ].map(copy),
    );
    await symlink(path.join(repositoryRoot, 'node_modules'), path.join(mirrorRoot, 'node_modules'));

    watcher = spawn(
        path.join(repositoryRoot, 'node_modules/.bin/vite'),
        ['build', '--watch', '--mode', 'development'],
        { cwd: mirrorRoot, stdio: ['ignore', 'pipe', 'pipe'] },
    );
    watcher.stdout.on('data', (chunk) => {
        watcherLog += chunk;
    });
    watcher.stderr.on('data', (chunk) => {
        watcherLog += chunk;
    });

    await waitFor(() => output('style-app'), 'initial Vite watch build');

    const cssEntry =
        'frontend_common/styles/templates/frontend-private-templates-pages-project-details.css';
    const cssSentinel = '.vite-watch-css{color:rgb(1 2 3)}';
    const restoreCss = await mutate(cssEntry, (source) => `${source}\n${cssSentinel}\n`);
    await waitFor(async () => {
        const built = await output(
            'style-template-frontend-private-templates-pages-project-details',
        );
        if (!built.includes('.vite-watch-css')) throw new Error('CSS sentinel absent');
    }, 'route CSS invalidation');
    await restoreCss();
    await waitFor(async () => {
        const built = await output(
            'style-template-frontend-private-templates-pages-project-details',
        );
        if (built.includes('.vite-watch-css')) throw new Error('deleted CSS retained');
    }, 'route CSS deletion invalidation');

    const templatePath = 'frontend_public/templates/pages/home.html';
    const restoreTemplate = await mutate(
        templatePath,
        (source) => `${source}\n<div class="top-[123px]"></div>\n`,
    );
    await waitFor(async () => {
        const built = await output('style-app');
        if (!built.includes('top-\\[123px\\]')) {
            throw new Error('Tailwind source sentinel absent');
        }
    }, 'Tailwind template-source invalidation');
    const buildsBeforeTemplateRestore = (watcherLog.match(/built in/g) ?? []).length;
    await restoreTemplate();
    await waitFor(() => {
        const completedBuilds = (watcherLog.match(/built in/g) ?? []).length;
        if (completedBuilds <= buildsBeforeTemplateRestore) {
            throw new Error('Tailwind source restore has not rebuilt');
        }
    }, 'Tailwind source restore');

    const unrelatedBefore = digest(await output('controller-feedback'));
    const restoreController = await mutate(
        'frontend_common/controllers/projects.js',
        (source) => `${source}\nconsole.info('__vite_watch_route__');\n`,
    );
    await waitFor(async () => {
        if (!(await output('controller-projects')).includes('__vite_watch_route__')) {
            throw new Error('route controller sentinel absent');
        }
    }, 'route-controller invalidation');
    const unrelatedAfter = digest(await output('controller-feedback'));
    if (unrelatedBefore !== unrelatedAfter) {
        throw new Error('An unrelated route controller changed');
    }
    await restoreController();

    const restoreShared = await mutate(
        'frontend_common/readiness.js',
        (source) => `${source}\nglobalThis.__viteWatchShared = true;\n`,
    );
    await waitFor(async () => {
        const files = await Promise.all(
            ['controller-feedback', 'controller-auth-form'].map(outputGraph),
        );
        if (!files.some((value) => value.includes('__viteWatchShared'))) {
            throw new Error('shared-module sentinel absent');
        }
    }, 'shared JavaScript invalidation');
    await restoreShared();

    process.stdout.write(
        'Vite watch verified CSS/import deletion, Tailwind source changes, ' +
        'shared JavaScript, controller invalidation, and route isolation.\n',
    );
} catch (error) {
    if (watcher) {
        process.stderr.write(`\nVite watcher output:\n${watcherLog}\n`);
    }
    throw error;
} finally {
    watcher?.kill('SIGTERM');
    await rm(mirrorRoot, { force: true, recursive: true });
}
