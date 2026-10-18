import type { ExportArtifact } from '@speleodb/api';
import type { ExportJob, ExportHistoryOptions } from '../../ts-types/domain/exports.ts';
import type { MockInstance } from 'vitest';
import { renderExportHistory, mergeExportJobs, exportRefreshDelay, requestedExportId, loadExportPage, init } from './user-exports.ts';
import { setBrowserUrl, startApiServer } from '../test/api-server.ts';
const ID = '11111111-1111-4111-8111-111111111111';
const ENDPOINT = '/api/v2/user/exports/';
const NOW = Date.parse('2026-09-15T12:00:00Z');
const FUTURE_EXPIRY = new Date(NOW + 60_000).toISOString();
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
beforeAll(async () => { originalUrl = window.location.href; server = await startApiServer(); });
beforeEach(() => { server.reset(); setBrowserUrl(`${server.origin}/exports/`); });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });
function job(overrides: Omit<Partial<ExportJob>, 'state' | 'artifact'> & {state?: string; artifact?: Partial<ExportArtifact> | null} = {}): ExportJob {
    return {
        id: ID,
        state: 'queued',
        stage: 'Collecting accessible data',
        completed_items: 2,
        total_items: 5,
        created_at: '2026-09-14T12:00:00Z',
        updated_at: '2026-09-14T12:00:00Z',
        summary: {},
        notification_state: 'pending',
        download_url: null,
        expired: false,
        ...overrides,
        artifact: overrides.artifact ? { filename: 'export.zip', size_bytes: 0, sha256: 'a'.repeat(64), ready_at: '2026-09-15T12:00:00Z', expires_at: FUTURE_EXPIRY, ...overrides.artifact } : null,
    } as ExportJob;
}

function render(jobs: ExportJob[], options: ExportHistoryOptions = {}) {
    const container = document.createElement('div');
    renderExportHistory(container, jobs, { endpoint: ENDPOINT, now: NOW, ...options });
    return container;
}

function exportPage() {
    const root = document.createElement('div');
    root.id = 'user-exports';
    root.innerHTML = `
        <form id="export-request-form">
            <input name="csrfmiddlewaretoken" value="export-test-csrf">
            <button id="export-create" type="submit"><span id="export-create-label"></span></button>
        </form>
        <div id="export-message"></div>
        <div id="export-history"></div>
        <button id="export-previous"></button>
        <button id="export-next"></button>
    `;
    document.body.append(root);
    return root;
}


describe('Export history presentation', () => {
    it('accepts an exact export link and ignores malformed identifiers', () => {
        expect(requestedExportId(`?export=${ID}`)).toBe(ID);
        expect(requestedExportId('?export=../../outside')).toBeNull();
        expect(requestedExportId('?page=2')).toBeNull();
    });

    it('shows a linked export only once when it is already on the page', () => {
        const container = render([job()], {
            linkedJob: job({ state: 'ready', download_url: `${ENDPOINT}${ID}/download/` }),
        });
        expect(container.querySelectorAll('[data-export-id]')).toHaveLength(1);
        expect(container.querySelectorAll('a')).toHaveLength(1);
        expect(container.textContent).toContain('Ready to download');
        expect(container.textContent).not.toContain('Queued');
        expect(container.textContent).not.toContain('Selected export');
    });

    it('merges and focuses an older linked job in the same list', () => {
        const recentId = '22222222-2222-4222-8222-222222222222';
        const history = document.createElement('div');
        document.body.append(history);
        try {
            const focused = renderExportHistory(history, [job({ id: recentId, state: 'failed' })], {
                endpoint: ENDPOINT,
                linkedJob: job({ state: 'running' }),
                focusId: ID,
            });
            expect(focused).toBe(true);
            expect(history.querySelectorAll('[data-export-id]')).toHaveLength(2);
            const linkedCard = history.querySelector<HTMLElement>(`[data-export-id="${ID}"]`)!;
            expect(linkedCard.parentElement).toBe(history);
            expect(linkedCard.textContent).toContain('Generating export');
            expect(document.activeElement).toBe(linkedCard);
            expect(history.querySelector<HTMLButtonElement>('[data-export-retry]')!.disabled).toBe(true);
        } finally {
            history.remove();
        }
    });

    it('deduplicates refresh results and uses the linked detail state for retry availability', () => {
        const failedId = '22222222-2222-4222-8222-222222222222';
        const queued = job();
        const page = [queued, job({ id: failedId, state: 'failed' }), queued];
        const ready = job({ state: 'ready' });
        const merged = mergeExportJobs(page, ready);
        expect(merged.map(item => item.id)).toEqual([ID, failedId]);
        expect(merged[0]!.state).toBe('ready');
        expect(page).toHaveLength(3);
        expect(queued.state).toBe('queued');
        const history = render(page, { linkedJob: ready });
        expect(history.querySelectorAll('[data-export-id]')).toHaveLength(2);
        expect(history.querySelector<HTMLButtonElement>('[data-export-retry]')!.disabled).toBe(false);
    });

    it('keeps ordinary history when a linked export is unavailable', () => {
        const history = render([job({ state: 'ready' })], { linkedJob: null, focusId: ID });
        expect(history.querySelectorAll('[data-export-id]')).toHaveLength(1);
        expect(history.querySelector<HTMLElement>(`[data-export-id="${ID}"]`)!).not.toBeNull();
        expect(history.querySelector<HTMLElement>('section')!).toBeNull();
    });

    it.each(['download', 'retry', 'card'])('preserves keyboard focus on a surviving %s during a history refresh', target => {
        const history = document.createElement('div');
        document.body.append(history);
        const current = target === 'retry'
            ? job({ state: 'failed' })
            : job({ state: 'ready', download_url: `${ENDPOINT}${ID}/download/` });
        const selector = target === 'download' ? 'a' : target === 'retry' ? '[data-export-retry]' : '[data-export-id]';
        try {
            renderExportHistory(history, [current], { endpoint: ENDPOINT, focusId: ID });
            history.querySelector<HTMLElement>(selector)!.focus();
            expect(document.activeElement).toBe(history.querySelector<HTMLElement>(selector)!);
            renderExportHistory(history, [current], { endpoint: ENDPOINT });
            expect(document.activeElement).toBe(history.querySelector<HTMLElement>(selector)!);
        } finally {
            history.remove();
        }
    });

    it('does not steal focus from outside history when refreshing cards', () => {
        const history = document.createElement('div');
        const outside = document.createElement('button');
        document.body.append(outside, history);
        try {
            outside.focus();
            renderExportHistory(history, [job({ state: 'failed' })], { endpoint: ENDPOINT });
            expect(document.activeElement).toBe(outside);
        } finally {
            history.remove();
            outside.remove();
        }
    });

    it('keeps a newer retry state from the page when the linked detail is older', () => {
        const queued = job({ updated_at: '2026-09-14T12:01:00Z' });
        const older = job({ state: 'failed' });
        expect(mergeExportJobs([queued], older)).toEqual([queued]);
        const history = render([queued], { linkedJob: older });
        expect(history.querySelectorAll('[data-export-id]')).toHaveLength(1);
        expect(history.textContent).toContain('Queued');
        expect(history.querySelector<HTMLButtonElement>('[data-export-retry]')!).toBeNull();
    });

    it.each(['queued', 'running', 'retry_wait'])('shows only the simple email message for %s exports', state => {
        expect(render([]).textContent).toContain('No current exports');
        const container = render([job({ state, stage: 'Exporting projects', completed_items: 0, total_items: 7 })]);
        expect(container.textContent).toContain('An email will be sent when ready to download.');
        expect(container.textContent).not.toContain('Exporting projects');
        expect(container.textContent).not.toContain('0 of 7 items');
        expect(container.querySelector<HTMLElement>('a')!).toBeNull();
        expect(container.querySelector<HTMLElement>('button')!).toBeNull();
    });

    it('renders a ready download independently of email failure', () => {
        const container = render([job({
            state: 'ready',
            notification_state: 'failed',
            download_url: 'https://unexpected.test/stolen',
            artifact: { size_bytes: 1024, expires_at: FUTURE_EXPIRY },
        })]);
        expect(container.textContent).toContain('Ready to download');
        expect(container.textContent).toContain('email could not be delivered');
        expect(container.querySelector<HTMLElement>('a')!.getAttribute('href')).toBe(`${ENDPOINT}${ID}/download/`);
    });

    it.each([
        [0, '0 bytes'],
        [750, '750 bytes'],
        [1500, '1.5 KB'],
        [125_000_000, '125 MB'],
        [2_500_000_000, '2.5 GB'],
        [3_000_000_000_000, '3 TB'],
        [-1, 'Size unavailable'],
    ])('presents archive size %s as %s', (size, label) => {
        const history = render([job({
            state: 'ready',
            artifact: { size_bytes: size, expires_at: FUTURE_EXPIRY },
        })]);
        expect(history.textContent).toContain(`${label} · Expires`);
    });

    it('gives empty-state guidance for generating an export', () => {
        expect(render([]).textContent).toContain('Generate an export above.');
    });

    it('keeps action labels readable while hiding decorative icons from assistive technology', () => {
        const history = render([
            job({ state: 'ready', download_url: `${ENDPOINT}${ID}/download/` }),
            job({ id: '22222222-2222-4222-8222-222222222222', state: 'failed' }),
        ]);
        expect(history.querySelector<HTMLElement>('a')!.textContent).toBe('Download ZIP');
        expect(history.querySelector<HTMLElement>('button')!.textContent).toBe('Retry export');
        expect(history.querySelectorAll('svg').length).toBeGreaterThan(0);
        expect([...history.querySelectorAll('svg')].every(svg => svg.getAttribute('aria-hidden') === 'true')).toBe(true);
    });

    it('clearly lists omissions and escapes every supplied name and reason', () => {
        const payload = '<img src=x onerror="alert(1)">';
        const container = render([job({
            state: 'partial',
            download_url: `${ENDPOINT}${ID}/download/`,
            summary: { omissions: [{ category: 'projects', name: payload, reason: '<script>bad()</script>' }] },
        })]);
        expect(container.textContent).toContain('Ready with omissions');
        expect(container.textContent).toContain('before relying on this backup');
        expect(container.textContent).toContain(payload);
        expect(container.textContent).toContain('<script>bad()</script>');
        expect(container.querySelector<HTMLElement>('img, script, [onerror]')!).toBeNull();
        expect(container.querySelectorAll('li')).toHaveLength(1);
        expect(container.querySelector<HTMLElement>('a')!).not.toBeNull();
    });

    it('hides expired cards and omits downloads for malformed entity identifiers', () => {
        const expired = render([job({ state: 'ready', expired: true, download_url: '/stale-link' })]);
        expect(expired.querySelector<HTMLElement>('[data-export-id]')!).toBeNull();
        expect(expired.textContent).toContain('No current exports');
        expect(expired.querySelector<HTMLElement>('a')!).toBeNull();
        const malformed = render([job({ state: 'ready', id: '../outside', download_url: '/stale-link' })]);
        expect(malformed.querySelector<HTMLElement>('a')!).toBeNull();
    });

    it.each([
        { expired: true },
        { artifact: { expires_at: new Date(NOW).toISOString() } },
        { expired: true, artifact: { expires_at: FUTURE_EXPIRY } },
    ])('excludes expired or deleted downloads from both list and email-link results: %j', unavailable => {
        const expired = job({ state: 'partial', ...unavailable });
        expect(mergeExportJobs([expired], expired, NOW)).toEqual([]);
        const history = render([], { linkedJob: expired, focusId: ID });
        expect(history.querySelector<HTMLElement>('[data-export-id]')!).toBeNull();
    });

    it.each(['queued', 'running', 'retry_wait'])('keeps an active %s job when an older artifact has expired', state => {
        const active = job({
            state,
            expired: true,
            artifact: { size_bytes: 123, expires_at: new Date(NOW - 1).toISOString() },
        });
        expect(mergeExportJobs([active], active, NOW)).toEqual([active]);
        const history = render([active]);
        expect(history.querySelector<HTMLElement>('[data-export-id]')!).not.toBeNull();
        expect(history.textContent).toContain('An email will be sent when ready to download.');
        expect(history.textContent).not.toContain('Export expired');
        expect(history.textContent).not.toContain('Expires');
    });

    it('removes downloads at expiry on the next render while preserving active work and failed retries', () => {
        const expiresAt = NOW + 1000;
        const ready = job({ state: 'ready', artifact: { size_bytes: 123, expires_at: new Date(expiresAt).toISOString() } });
        const failed = job({ id: '22222222-2222-4222-8222-222222222222', state: 'failed' });
        const active = job({ id: '33333333-3333-4333-8333-333333333333' });
        const jobs = [ready, failed, active];
        const history = render(jobs);
        expect(history.querySelectorAll('[data-export-id]')).toHaveLength(3);
        renderExportHistory(history, jobs, { endpoint: ENDPOINT, linkedJob: ready, now: expiresAt });
        expect(history.querySelectorAll('[data-export-id]')).toHaveLength(2);
        expect(history.querySelector<HTMLElement>(`[data-export-id="${ID}"]`)!).toBeNull();
        expect(history.querySelector<HTMLButtonElement>('[data-export-retry]')!).not.toBeNull();
        expect(history.textContent).toContain('An email will be sent when ready to download.');
    });

    it('schedules expiry while idle, caps distant timers, and avoids invalid or elapsed deadlines', () => {
        const ready = job({ state: 'ready', artifact: { expires_at: FUTURE_EXPIRY } });
        expect(exportRefreshDelay([ready], false, NOW)).toBe(60_000);
        expect(exportRefreshDelay([ready], true, NOW)).toBe(5000);
        expect(exportRefreshDelay([ready], false, Date.parse(FUTURE_EXPIRY))).toBeNull();
        expect(exportRefreshDelay([job({ state: 'ready', artifact: { expires_at: 'invalid' } })], false, NOW)).toBeNull();
        const distant = job({ state: 'ready', artifact: { expires_at: new Date(NOW + 2 ** 32).toISOString() } });
        expect(exportRefreshDelay([distant], false, NOW)).toBe(2 ** 31 - 1);
        const imminent = job({ state: 'ready', artifact: { expires_at: new Date(NOW + 1).toISOString() } });
        expect(exportRefreshDelay([imminent], true, NOW)).toBe(1);
        expect(exportRefreshDelay([], false, NOW)).toBeNull();
    });

    it('allows a failed export retry and prevents concurrent retries', () => {
        const failed = job({ state: 'failed' });
        expect(render([failed]).querySelector<HTMLButtonElement>('[data-export-retry]')!.disabled).toBe(false);
        expect(render([failed, job({ id: '22222222-2222-4222-8222-222222222222' })])
            .querySelector<HTMLButtonElement>('[data-export-retry]')!.disabled).toBe(true);
        expect(render([failed], { busy: true }).querySelector<HTMLButtonElement>('[data-export-retry]')!.disabled).toBe(true);
    });

    it('never displays a worker exception as public failed-state content', () => {
        const container = render([job({ state: 'failed', summary: { error: 'private/internal/location' } })]);
        expect(container.textContent).toContain('Export failed');
        expect(container.textContent).not.toContain('private/internal/location');
    });


});

it.each([
    { page: 2, pageStatus: 404, firstStatus: 200, expectedStatus: 200, pages: [2, 1] },
    { page: 2, pageStatus: 404, firstStatus: 404, expectedStatus: 404, pages: [2, 1] },
    { page: 2, pageStatus: 403, firstStatus: 200, expectedStatus: 403, pages: [2] },
    { page: 1, pageStatus: 404, firstStatus: 404, expectedStatus: 404, pages: [1] },
])('recovers an expired page once through the generated pagination operation: %j', async scenario => {
    const data = { results: [], previous: null, next: null };
    server.handle(request => { const page = Number(new URL(request.path, server.origin).searchParams.get('page')); const status = page === 1 ? scenario.firstStatus : scenario.pageStatus; return { status, json: status === 200 ? data : { detail: 'History unavailable.' } }; });
    const first = `${server.origin}${ENDPOINT}`;
    const result = loadExportPage(scenario.page === 1 ? first : `${first}?page=${scenario.page}`, first);
    if (scenario.expectedStatus === 200) await expect(result).resolves.toEqual({ url: first, data });
    else await expect(result).rejects.toMatchObject({ status: scenario.expectedStatus });
    expect(server.requests.map(request => Number(new URL(request.path, server.origin).searchParams.get('page')))).toEqual(scenario.pages);
});

it('rejects foreign, unrelated and malformed pagination URLs before transport', async () => {
    const first = `${server.origin}${ENDPOINT}`;
    for (const target of ['https://outside.test/exports/', `${server.origin}/other/`, `${first}?page=0`, `${first}?page=1.5`]) await expect(loadExportPage(target, first)).rejects.toThrow('Invalid export page');
    expect(server.requests).toHaveLength(0);
});

describe('Export request and refresh budgets', () => {
    let root: HTMLElement;
    let windowListeners: MockInstance<Window['addEventListener']>;
    let documentListeners: MockInstance<Document['addEventListener']>;
    const empty = { results: [], previous: null, next: null };
    function history() { return root.querySelector<HTMLElement>('#export-history')!; }
    function message() { return root.querySelector<HTMLElement>('#export-message')!.textContent; }
    function createButton() { return root.querySelector<HTMLButtonElement>('#export-create')!; }
    async function settled() { await vi.waitFor(() => expect(history().getAttribute('aria-busy')).toBe('false')); }
    async function tick(delay: number, requestCount: number) {
        await vi.advanceTimersByTimeAsync(delay);
        await vi.waitFor(() => expect(server.requests).toHaveLength(requestCount));
        await settled();
    }
    beforeEach(() => {
        vi.useFakeTimers(); vi.setSystemTime(NOW);
        windowListeners = vi.spyOn(window, 'addEventListener'); documentListeners = vi.spyOn(document, 'addEventListener');
        root = exportPage(); server.reply({ json: empty });
    });
    afterEach(async () => {
        window.dispatchEvent(new Event('pagehide')); await vi.advanceTimersByTimeAsync(0);
        for (const [event, listener, options] of windowListeners.mock.calls) if (['pagehide', 'pageshow'].includes(event)) window.removeEventListener(event, listener, options);
        for (const [event, listener, options] of documentListeners.mock.calls) if (event === 'visibilitychange') document.removeEventListener(event, listener, options);
        root.remove(); vi.clearAllTimers(); vi.useRealTimers(); vi.restoreAllMocks();
    });

    it('submits a generated export request once, focuses the resulting job and preserves CSRF', async () => {
        let requested = false;
        server.handle(request => {
            if (request.method === 'POST') requested = true;
            return { status: request.method === 'POST' ? 202 : 200, json: request.method === 'POST' || request.path === `${ENDPOINT}${ID}/` ? job() : { ...empty, results: requested ? [job()] : [] } };
        });
        await init(); expect(createButton().disabled).toBe(false);
        root.querySelector<HTMLFormElement>('form')!.requestSubmit(); root.querySelector<HTMLFormElement>('form')!.requestSubmit();
        await vi.waitFor(() => expect(root.querySelector<HTMLElement>('[data-export-id]')?.dataset.exportId).toBe(ID)); await settled();
        const requests = server.requests.filter(request => request.method === 'POST');
        expect(requests).toHaveLength(1); expect(requests[0]).toMatchObject({ path: ENDPOINT, body: '', headers: { 'x-csrftoken': 'export-test-csrf' } });
        expect(message()).toContain('We will email you when it is ready.'); expect(createButton().disabled).toBe(true);
        expect(new URL(window.location.href).searchParams.get('export')).toBe(ID);
    });

    it('retries the selected failed export using the generated retry route', async () => {
        let retried = false;
        server.handle(request => {
            if (request.method === 'POST') { retried = true; return { status: 202, json: job() }; }
            return { json: request.path === `${ENDPOINT}${ID}/` ? job() : { ...empty, results: [job({ state: retried ? 'queued' : 'failed' })] } };
        });
        await init(); root.querySelector<HTMLButtonElement>('[data-export-retry]')!.click();
        await vi.waitFor(() => expect(server.requests.some(request => request.method === 'POST')).toBe(true));
        expect(server.requests.find(request => request.method === 'POST')).toMatchObject({ path: `${ENDPOINT}${ID}/retry/`, body: '' });
        await settled();
    });

    it('stops after five HTTP failures with capped exponential backoff', async () => {
        server.reply({ status: 503, json: { detail: 'Exports unavailable.' } }); await init();
        for (const [index, delay] of [5000, 10_000, 20_000, 30_000].entries()) await tick(delay, index + 2);
        expect(message()).toContain('Reload this page or try again.'); expect(createButton().disabled).toBe(false);
        document.dispatchEvent(new Event('visibilitychange')); await vi.advanceTimersByTimeAsync(120_000);
        expect(server.requests).toHaveLength(5); expect(vi.getTimerCount()).toBe(0);
    });

    it('resets failure backoff after a successful active-job refresh', async () => {
        server.reply({ status: 503, json: { detail: 'Unavailable' } }); await init(); await tick(5000, 2);
        server.reply({ json: { ...empty, results: [job()] } }); await tick(10_000, 3);
        expect(message()).toBe(''); expect(history().textContent).toContain('Queued');
        server.reply({ status: 503, json: { detail: 'Unavailable' } }); await tick(5000, 4); await tick(5000, 5);
    });

    it('preserves backoff on visibility and polls successful active jobs beyond the failure limit', async () => {
        server.reply({ status: 503, json: { detail: 'Unavailable' } }); await init();
        document.dispatchEvent(new Event('visibilitychange')); await vi.advanceTimersByTimeAsync(4999); expect(server.requests).toHaveLength(1);
        server.reply({ json: { ...empty, results: [job()] } }); await tick(1, 2);
        for (let index = 0; index < 6; index += 1) await tick(5000, index + 3);
        expect(message()).toBe('');
    });

    it('times out a hanging real HTTP response within the existing request budget', async () => {
        server.handle(() => new Promise(() => {}));
        const url = `${server.origin}${ENDPOINT}`; const request = loadExportPage(url, url);
        const rejected = expect(request).rejects.toThrow('The export request timed out.');
        await vi.waitFor(() => expect(server.requests).toHaveLength(1));
        await vi.advanceTimersByTimeAsync(30_000); await rejected; expect(vi.getTimerCount()).toBe(0);
    });

    it('bounds both requests for a linked export and releases its busy state', async () => {
        setBrowserUrl(`${server.origin}/exports/?export=${ID}`); server.handle(() => new Promise(() => {}));
        const pending = init(); await vi.waitFor(() => expect(server.requests).toHaveLength(2));
        expect(history().getAttribute('aria-busy')).toBe('true'); await vi.advanceTimersByTimeAsync(30_000); await pending;
        expect(history().getAttribute('aria-busy')).toBe('false'); expect(message()).toContain('timed out');
    });

    it.each([403, 404])('stops retrying inaccessible linked export HTTP%s while polling active history', async status => {
        setBrowserUrl(`${server.origin}/exports/?export=${ID}`);
        server.handle(request => request.path === `${ENDPOINT}${ID}/` ? { status, json: { detail: 'This export is inaccessible.' } } : { json: { ...empty, results: [job()] } });
        await init(); for (let index = 0; index < 3; index += 1) await tick(5000, index + 3);
        expect(server.requests.filter(request => request.path === `${ENDPOINT}${ID}/`)).toHaveLength(1);
        expect(root.querySelectorAll('[data-export-id]')).toHaveLength(1);
    });

    it('cancels navigation-owned HTTP requests without retrying', async () => {
        server.handle(() => new Promise(() => {})); const pending = init();
        await vi.waitFor(() => expect(server.requests).toHaveLength(1)); window.dispatchEvent(new Event('pagehide')); await pending;
        expect(message()).toBe(''); expect(history().getAttribute('aria-busy')).toBe('false');
        await vi.advanceTimersByTimeAsync(120_000); expect(server.requests).toHaveLength(1); expect(vi.getTimerCount()).toBe(0);
    });

    it('releases caller cancellation listeners and rejects cancelled page loading', async () => {
        const controller = new AbortController(); const remove = vi.spyOn(controller.signal, 'removeEventListener');
        const deadlines = vi.spyOn(window, 'setTimeout'); const cleared = vi.spyOn(window, 'clearTimeout');
        const url = `${server.origin}${ENDPOINT}`; await loadExportPage(url, url, { signal: controller.signal });
        expect(remove).toHaveBeenCalledWith('abort', expect.any(Function));
        server.handle(() => new Promise(() => {})); const pending = loadExportPage(url, url, { signal: controller.signal });
        const rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
        await vi.waitFor(() => expect(server.requests).toHaveLength(2)); controller.abort(); await rejected;
        expect(remove).toHaveBeenCalledTimes(2);
        for (const [index, call] of deadlines.mock.calls.entries()) if (call[1] === 30_000) expect(cleared).toHaveBeenCalledWith(deadlines.mock.results[index]!.value);
    });

    it('times out a POST without automatically repeating the mutation', async () => {
        server.handle(request => request.method === 'POST' ? new Promise(() => {}) : { json: empty });
        await init(); root.querySelector<HTMLFormElement>('form')!.requestSubmit();
        await vi.waitFor(() => expect(server.requests.some(request => request.method === 'POST')).toBe(true));
        await vi.advanceTimersByTimeAsync(30_000); await vi.waitFor(() => expect(createButton().disabled).toBe(false));
        expect(message()).toContain('timed out'); await vi.advanceTimersByTimeAsync(120_000);
        expect(server.requests.filter(request => request.method === 'POST')).toHaveLength(1);
    });

    it('uses generated pagination and keeps external pagination links inactive', async () => {
        server.reply({ json: { ...empty, next: `${ENDPOINT}?page=2` } }); await init();
        server.reply({ json: { ...empty, previous: 'https://outside.test/exports/?page=1' } }); root.querySelector<HTMLButtonElement>('#export-next')!.click();
        await vi.waitFor(() => expect(server.requests).toHaveLength(2)); await settled();
        expect(server.requests[1]!.path).toBe(`${ENDPOINT}?page=2`); expect(root.querySelector<HTMLButtonElement>('#export-previous')!.hidden).toBe(true);
    });

    it('bounds transient linked-export failures while retaining successful history', async () => {
        setBrowserUrl(`${server.origin}/exports/?export=${ID}`);
        server.handle(request => request.path === `${ENDPOINT}${ID}/`
            ? { status: 429, json: { detail: 'Too many requests.' } }
            : { json: { ...empty, results: [job()] } });
        await init();
        for (const [index, delay] of [5000, 10_000, 20_000, 30_000].entries()) await tick(delay, (index + 2) * 2);
        expect(message()).toContain('Reload this page'); expect(history().textContent).toContain('Queued');
        await vi.advanceTimersByTimeAsync(120_000); expect(server.requests).toHaveLength(10);
    });

    it('starts a fresh refresh budget after an explicit export submission', async () => {
        server.reply({ status: 503, json: { detail: 'Unavailable' } }); await init();
        for (const [index, delay] of [5000, 10_000, 20_000, 30_000].entries()) await tick(delay, index + 2);
        expect(createButton().disabled).toBe(false);
        server.handle(request => request.method === 'POST' ? { status: 202, json: job() } : { status: 503, json: { detail: 'Still unavailable' } });
        root.querySelector<HTMLFormElement>('form')!.requestSubmit();
        await vi.waitFor(() => expect(server.requests).toHaveLength(8)); await settled();
        expect(message()).toBe('Still unavailable'); await tick(5000, 10);
        expect(server.requests.filter(request => request.method === 'POST')).toHaveLength(1);
    });

    it('starts a fresh refresh budget after explicit pagination', async () => {
        server.reply({ json: { ...empty, next: `${ENDPOINT}?page=2` } }); await init();
        server.reply({ status: 503, json: { detail: 'Unavailable' } }); root.querySelector<HTMLButtonElement>('#export-next')!.click();
        await vi.waitFor(() => expect(server.requests).toHaveLength(2)); await settled();
        for (const [index, delay] of [5000, 10_000, 20_000, 30_000].entries()) await tick(delay, index + 3);
        expect(message()).toContain('Reload this page');
        root.querySelector<HTMLButtonElement>('#export-next')!.click();
        await vi.waitFor(() => expect(server.requests).toHaveLength(7)); await settled(); expect(message()).toBe('Unavailable');
        await tick(5000, 8);
        server.reply({ json: empty }); root.querySelector<HTMLButtonElement>('#export-next')!.click();
        await vi.waitFor(() => expect(server.requests).toHaveLength(9)); await settled(); expect(message()).toBe('');
    });

    it('removes newly expired downloads after the network retry budget is exhausted', async () => {
        const expiresAt = NOW + 70_000;
        server.reply({ json: { ...empty, results: [job({ state: 'ready', artifact: { expires_at: new Date(expiresAt).toISOString() } })], next: `${ENDPOINT}?page=2` } });
        await init(); server.reply({ status: 503, json: { detail: 'Unavailable' } }); root.querySelector<HTMLButtonElement>('#export-next')!.click();
        await vi.waitFor(() => expect(server.requests).toHaveLength(2)); await settled();
        for (const [index, delay] of [5000, 10_000, 20_000, 30_000].entries()) await tick(delay, index + 3);
        expect(root.querySelector('[data-export-id]')).not.toBeNull();
        await vi.advanceTimersByTimeAsync(expiresAt - Date.now());
        expect(root.querySelector('[data-export-id]')).toBeNull(); expect(server.requests).toHaveLength(6);
    });

});
