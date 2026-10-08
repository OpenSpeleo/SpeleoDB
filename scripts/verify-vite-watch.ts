import type { ChildProcessByStdio } from 'node:child_process';
import type { Readable } from 'node:stream';
import type { Manifest, ManifestChunk } from 'vite';
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

const delay = (milliseconds: number) =>
    new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitFor<T>(assertion: () => T | Promise<T>, label: string, timeout = 20_000) {
    const deadline = Date.now() + timeout;
    let lastError: unknown;
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

async function copy(relativePath: string) {
    const destination = path.join(mirrorRoot, relativePath);
    await mkdir(path.dirname(destination), { recursive: true });
    await cp(
        path.join(repositoryRoot, relativePath),
        destination,
        { recursive: true },
    );
}

async function manifestEntry(logicalName: string) {
    const manifest = JSON.parse(await readFile(manifestPath, 'utf8')) as Manifest;
    const matches = Object.values(manifest).filter(
        (entry) => entry.isEntry && entry.name === logicalName,
    );
    if (matches.length !== 1) {
        throw new Error(`Expected one manifest entry for ${logicalName}`);
    }
    return path.join(outputRoot, matches[0]!.file);
}

async function output(logicalName: string) {
    return readFile(await manifestEntry(logicalName), 'utf8');
}

async function outputGraph(logicalName: string) {
    const manifest = JSON.parse(await readFile(manifestPath, 'utf8')) as Manifest;
    const match = Object.entries(manifest).find(
        ([, entry]) => entry.isEntry && entry.name === logicalName,
    );
    if (!match) throw new Error(`Missing manifest entry for ${logicalName}`);
    const values: string[] = [];
    const visited = new Set<string>();
    async function visit([key, entry]: [string, ManifestChunk]): Promise<void> {
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

function digest(value: string) {
    return createHash('sha256').update(value).digest('hex');
}

async function mutate(relativePath: string, transform: (source: string) => string) {
    const absolutePath = path.join(mirrorRoot, relativePath);
    const original = await readFile(absolutePath, 'utf8');
    await writeFile(absolutePath, transform(original));
    return async () => writeFile(absolutePath, original);
}

let watcher: ChildProcessByStdio<null, Readable, Readable> | undefined;
let watcherLog = '';
try {
    await Promise.all(
        [
            'vite.config.ts',
            'package.json',
            'scripts/vite-development.ts',
            'frontend_common',
            'frontend_errors',
            'frontend_private',
            'frontend_public',
            'tailwind_css',
            'speleodb/gis/geometry_contract.json',
            'speleodb/templates',
            'speleodb/surveys/templatetags/project_types.py',
        ].map(copy),
    );
    await symlink(path.join(repositoryRoot, 'node_modules'), path.join(mirrorRoot, 'node_modules'));

    watcher = spawn(
        process.execPath,
        [path.join(repositoryRoot, 'node_modules/.bin/vite'), 'build', '--watch', '--mode', 'development'],
        { cwd: mirrorRoot, stdio: ['ignore', 'pipe', 'pipe'] },
    );
    watcher.stdout.on('data', (chunk: Buffer) => {
        watcherLog += chunk as unknown as string;
    });
    watcher.stderr.on('data', (chunk: Buffer) => {
        watcherLog += chunk as unknown as string;
    });

    await waitFor(() => output('style-app'), 'initial Vite watch build');
    const firstManifest = JSON.parse(await readFile(manifestPath, 'utf8')) as Manifest;
    const manifestFiles = (manifest: Manifest) => [...new Set(Object.values(manifest)
        .flatMap(entry => [entry.file, ...(entry.assets ?? []), ...(entry.css ?? [])]))];
    const retainedOutputs = await Promise.all(manifestFiles(firstManifest).map(async file => ({
        file,
        hash: digest(await readFile(path.join(outputRoot, file), 'utf8')),
    })));
    const firstWorker = manifestFiles(firstManifest).find(file => file.includes('geojson_worker'));
    if (!firstWorker?.startsWith('assets/dev/')) throw new Error('Worker outside development generation');
    const reloadChunk = Object.values(firstManifest).find(entry => entry.src === 'frontend_common/development/reload.ts');
    if (!reloadChunk || !(await readFile(path.join(outputRoot, reloadChunk.file), 'utf8')).includes('speleo_dev_reload_target')) {
        throw new Error('Development reload client not emitted');
    }

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
        'frontend_common/controllers/projects.ts',
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
        'frontend_common/readiness.ts',
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

    // A build error must leave the completed manifest and old lazy graph intact.
    await waitFor(async () => {
        if ((await outputGraph('controller-feedback')).includes('__viteWatchShared')) {
            throw new Error('Shared source restore has not rebuilt');
        }
    }, 'shared-module restoration');
    const beforeAdmin = await readFile(manifestPath, 'utf8');
    const restoreAdmin = await mutate('speleodb/templates/admin/experiment_field_widget.html', source => `${source}\n<!-- Watch text-only edit -->\n`);
    await waitFor(async () => {
        if (await readFile(manifestPath, 'utf8') === beforeAdmin) throw new Error('Admin template has not rebuilt');
    }, 'admin template text-only invalidation');
    const beforeAdminRestore = await readFile(manifestPath, 'utf8');
    await restoreAdmin();
    await waitFor(async () => {
        if (await readFile(manifestPath, 'utf8') === beforeAdminRestore) throw new Error('Admin template restore has not rebuilt');
    }, 'admin template restoration');
    const publishedBeforeFailure = await readFile(manifestPath, 'utf8');
    const logBeforeFailure = watcherLog.length;
    const restoreFailure = await mutate('frontend_common/controllers/projects.ts', source => `${source}\nexport const = ;\n`);
    await waitFor(() => {
        if (!/Build failed|ERROR|error:/i.test(watcherLog.slice(logBeforeFailure))) {
            throw new Error('Expected build error not yet reported');
        }
    }, 'failed build');
    if (await readFile(manifestPath, 'utf8') !== publishedBeforeFailure) {
        throw new Error('Failed build published a manifest');
    }
    await restoreFailure();
    await waitFor(async () => {
        if (await readFile(manifestPath, 'utf8') === publishedBeforeFailure) {
            throw new Error('Restored build not published');
        }
    }, 'successful publication after failure');
    for (const retained of retainedOutputs) {
        if (digest(await readFile(path.join(outputRoot, retained.file), 'utf8')) !== retained.hash) {
            throw new Error(`Previously published asset changed: ${retained.file}`);
        }
    }
    const finalManifest = JSON.parse(await readFile(manifestPath, 'utf8')) as Manifest;
    const finalWorker = manifestFiles(finalManifest).find(file => file.includes('geojson_worker'));
    const finalApp = Object.values(finalManifest).find(entry => entry.name === 'app');
    if (!finalApp || !finalWorker || finalWorker === firstWorker
        || finalWorker.split('/').slice(0, 4).join('/') !== finalApp.file.split('/').slice(0, 4).join('/')) {
        throw new Error('Published worker does not belong to the current app generation');
    }

    process.stdout.write(
        'Vite watch verified CSS/import deletion, Tailwind source changes, ' +
        'shared JavaScript, controller invalidation, route isolation, failed-build publication, ' +
        'immutable prior assets and worker generation ownership.\n',
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
