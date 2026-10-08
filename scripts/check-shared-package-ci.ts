import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const PACKAGES = {
    '@speleodb/map-core': 'OpenSpeleo/SpeleoDB-TS-MapCore',
    '@speleodb/map-viewer': 'OpenSpeleo/SpeleoDB-TS-MapViewer',
};
const MAX_WAIT_MS = 30 * 60 * 1000;
const POLL_MS = 30 * 1000;

interface Manifest {
    dependencies?: Record<string, string>;
    overrides?: Record<string, string>;
}

interface Runtime {
    fetch: (url: string, init: RequestInit) => Promise<Response>;
    now: () => number;
    sleep: (ms: number) => Promise<void>;
    log: (message: string) => void;
    token?: string | undefined;
}

interface Pin {
    name: string;
    repository: string;
    sha: string;
}

interface WorkflowRun {
    id: number;
    head_sha: string;
    event: string;
    status: string;
    conclusion: string | null;
    html_url: string;
}

function pinsFromManifest(manifest: Manifest): Pin[] {
    const pins = Object.entries(PACKAGES).map(([name, repository]) => {
        const prefix = `git+https://github.com/${repository}.git#`;
        const value = manifest.dependencies?.[name] ?? '';
        const sha = value.slice(prefix.length);
        if (!value.startsWith(prefix) || !/^[a-f0-9]{40}$/.test(sha)) {
            throw new Error(`${name} must pin ${prefix}<full 40-character SHA>`);
        }
        return { name, repository, sha };
    });
    if (manifest.overrides?.['@speleodb/map-core'] !== manifest.dependencies?.['@speleodb/map-core']) {
        throw new Error('The map-core override must match its direct dependency exactly.');
    }
    return pins;
}

/** Runs before dependency installation; only Bun built-ins and GitHub's API are needed. */
export async function checkSharedPackageCI(manifest: Manifest, runtime: Runtime): Promise<void> {
    const pins = pinsFromManifest(manifest);
    const deadline = runtime.now() + MAX_WAIT_MS;
    const remaining = (): number => {
        const ms = deadline - runtime.now();
        if (ms <= 0) throw new Error('Shared package CI did not pass within 30 minutes.');
        return ms;
    };
    const get = async <T>(path: string): Promise<T> => {
        const response = await runtime.fetch(`https://api.github.com/repos/${path}`, {
            headers: {
                Accept: 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
                ...(runtime.token ? { Authorization: `Bearer ${runtime.token}` } : {}),
            },
            signal: AbortSignal.timeout(Math.min(30_000, remaining())),
        });
        if (!response.ok) {
            throw new Error(`GitHub ${path}: HTTP ${response.status}. Cannot verify shared package CI.`);
        }
        const body = await response.json() as T;
        remaining();
        return body;
    };

    // Verify both revisions before polling. A nonexistent pin must fail immediately.
    for (const pin of pins) {
        const commit = await get<{ sha: string }>(`${pin.repository}/commits/${pin.sha}`);
        if (commit.sha !== pin.sha) throw new Error(`${pin.name}: GitHub returned a different commit.`);
        runtime.log(`${pin.name}: published commit ${pin.sha} exists.`);
    }

    for (;;) {
        let allPassed = true;
        for (const pin of pins) {
            // Only the package's verification workflow on the exact pushed commit counts.
            // Inspect every page, then select the newest run (reruns update that run).
            const runs: WorkflowRun[] = [];
            for (let page = 1; ; page++) {
                const result = await get<{ workflow_runs: WorkflowRun[] }>(
                    `${pin.repository}/actions/workflows/ci.yml/runs?head_sha=${pin.sha}&event=push&per_page=100&page=${page}`,
                );
                if (!Array.isArray(result.workflow_runs) || result.workflow_runs.some(item =>
                    !item || !Number.isSafeInteger(item.id) || item.id <= 0
                    || typeof item.head_sha !== 'string' || typeof item.event !== 'string'
                    || typeof item.status !== 'string' || typeof item.html_url !== 'string'
                    || (item.conclusion !== null && typeof item.conclusion !== 'string'))) {
                    throw new Error(`${pin.name}: invalid GitHub workflow response.`);
                }
                runs.push(...result.workflow_runs);
                if (result.workflow_runs.length < 100) break;
            }
            const run = runs.filter(item => item.head_sha === pin.sha && item.event === 'push')
                .sort((a, b) => b.id - a.id)[0];
            if (!run) {
                runtime.log(`${pin.name}: waiting for ci.yml push verification at ${pin.sha}.`);
                allPassed = false;
            } else if (run.status === 'completed') {
                if (run.conclusion !== 'success') {
                    throw new Error(`${pin.name}: verification ${run.conclusion ?? 'without a conclusion'}: ${run.html_url}`);
                }
                runtime.log(`${pin.name}: verification passed: ${run.html_url}`);
            } else {
                runtime.log(`${pin.name}: verification ${run.status}: ${run.html_url}`);
                allPassed = false;
            }
        }
        remaining();
        if (allPassed) return;
        await runtime.sleep(Math.min(POLL_MS, remaining()));
    }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    try {
        const manifest = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')) as Manifest;
        await checkSharedPackageCI(manifest, {
            fetch: (url, init) => fetch(url, init),
            now: () => performance.now(),
            sleep: ms => new Promise(done => setTimeout(done, ms)),
            log: message => console.log(message),
            token: process.env.GITHUB_TOKEN,
        });
    } catch (error) {
        console.error(error instanceof Error ? error.message : String(error));
        process.exitCode = 1;
    }
}
