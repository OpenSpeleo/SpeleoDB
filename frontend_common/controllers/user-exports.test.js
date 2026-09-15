import { createServer } from 'node:http';

import { renderExportHistory } from './user-exports.js';
import { mergeExportJobs } from './user-exports.js';
import { exportRefreshDelay } from './user-exports.js';
import { requestedExportId } from './user-exports.js';
import { loadExportPage } from './user-exports.js';
import { init } from './user-exports.js';

const ID = '11111111-1111-4111-8111-111111111111';
const ENDPOINT = '/api/v2/user/exports/';
const NOW = Date.parse('2026-09-15T12:00:00Z');
const FUTURE_EXPIRY = new Date(NOW + 60_000).toISOString();

function job(overrides = {}) {
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
        artifact: null,
        download_url: null,
        expired: false,
        ...overrides,
    };
}

function render(jobs, options = {}) {
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

function exportResponse(data) {
    return { ok: true, json: async () => data };
}

describe('Export history presentation', () => {
    it.each([
        { page: '?page=2', pageStatus: 404, firstStatus: 200, expectedStatus: 200, expectedRequests: ['?page=2', ''] },
        { page: '?page=2', pageStatus: 404, firstStatus: 404, expectedStatus: 404, expectedRequests: ['?page=2', ''] },
        { page: '?page=2', pageStatus: 403, firstStatus: 200, expectedStatus: 403, expectedRequests: ['?page=2'] },
        { page: '', pageStatus: 404, firstStatus: 404, expectedStatus: 404, expectedRequests: [''] },
    ])('recovers an expired history page once without retrying other errors: %j', async scenario => {
        const requests = [];
        const data = { results: [], previous: null, next: null };
        const server = createServer((request, response) => {
            const query = new URL(request.url, 'http://localhost').search;
            requests.push(query);
            const status = query ? scenario.pageStatus : scenario.firstStatus;
            response.writeHead(status, { 'Content-Type': 'application/json' });
            response.end(JSON.stringify(status === 200 ? data : { detail: 'History unavailable.' }));
        });
        await new Promise((resolve, reject) => {
            server.once('error', reject);
            server.listen(0, '127.0.0.1', resolve);
        });
        try {
            const firstPage = `http://127.0.0.1:${server.address().port}${ENDPOINT}`;
            const result = loadExportPage(`${firstPage}${scenario.page}`, firstPage);
            if (scenario.expectedStatus === 200) {
                await expect(result).resolves.toEqual({ url: firstPage, data });
            } else {
                await expect(result).rejects.toMatchObject({ status: scenario.expectedStatus });
            }
            expect(requests).toEqual(scenario.expectedRequests);
        } finally {
            server.closeAllConnections();
            await new Promise(resolve => server.close(resolve));
        }
    });

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
            const linkedCard = history.querySelector(`[data-export-id="${ID}"]`);
            expect(linkedCard.parentElement).toBe(history);
            expect(linkedCard.textContent).toContain('Generating export');
            expect(document.activeElement).toBe(linkedCard);
            expect(history.querySelector('[data-export-retry]').disabled).toBe(true);
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
        expect(merged[0].state).toBe('ready');
        expect(page).toHaveLength(3);
        expect(queued.state).toBe('queued');
        const history = render(page, { linkedJob: ready });
        expect(history.querySelectorAll('[data-export-id]')).toHaveLength(2);
        expect(history.querySelector('[data-export-retry]').disabled).toBe(false);
    });

    it('keeps ordinary history when a linked export is unavailable', () => {
        const history = render([job({ state: 'ready' })], { linkedJob: null, focusId: ID });
        expect(history.querySelectorAll('[data-export-id]')).toHaveLength(1);
        expect(history.querySelector(`[data-export-id="${ID}"]`)).not.toBeNull();
        expect(history.querySelector('section')).toBeNull();
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
            history.querySelector(selector).focus();
            expect(document.activeElement).toBe(history.querySelector(selector));
            renderExportHistory(history, [current], { endpoint: ENDPOINT });
            expect(document.activeElement).toBe(history.querySelector(selector));
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
        expect(history.querySelector('[data-export-retry]')).toBeNull();
    });

    it.each(['queued', 'running', 'retry_wait'])('shows only the simple email message for %s exports', state => {
        expect(render([]).textContent).toContain('No current exports');
        const container = render([job({ state, stage: 'Exporting projects', completed_items: 0, total_items: 7 })]);
        expect(container.textContent).toContain('An email will be sent when ready to download.');
        expect(container.textContent).not.toContain('Exporting projects');
        expect(container.textContent).not.toContain('0 of 7 items');
        expect(container.querySelector('a')).toBeNull();
        expect(container.querySelector('button')).toBeNull();
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
        expect(container.querySelector('a').getAttribute('href')).toBe(`${ENDPOINT}${ID}/download/`);
    });

    it.each([
        [0, '0 bytes'],
        [750, '750 bytes'],
        [1500, '1.5 KB'],
        [125_000_000, '125 MB'],
        [2_500_000_000, '2.5 GB'],
        [3_000_000_000_000, '3 TB'],
        [null, 'Size unavailable'],
        [-1, 'Size unavailable'],
        ['invalid', 'Size unavailable'],
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
        expect(history.querySelector('a').textContent).toBe('Download ZIP');
        expect(history.querySelector('button').textContent).toBe('Retry export');
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
        expect(container.querySelector('img, script, [onerror]')).toBeNull();
        expect(container.querySelectorAll('li')).toHaveLength(1);
        expect(container.querySelector('a')).not.toBeNull();
    });

    it('hides expired cards and omits downloads for malformed entity identifiers', () => {
        const expired = render([job({ state: 'ready', expired: true, download_url: '/stale-link' })]);
        expect(expired.querySelector('[data-export-id]')).toBeNull();
        expect(expired.textContent).toContain('No current exports');
        expect(expired.querySelector('a')).toBeNull();
        const malformed = render([job({ state: 'ready', id: '../outside', download_url: '/stale-link' })]);
        expect(malformed.querySelector('a')).toBeNull();
    });

    it.each([
        { expired: true },
        { artifact: { expires_at: new Date(NOW).toISOString() } },
        { artifact: { expires_at: FUTURE_EXPIRY, deleted_at: new Date(NOW).toISOString() } },
    ])('excludes expired or deleted downloads from both list and email-link results: %j', unavailable => {
        const expired = job({ state: 'partial', ...unavailable });
        expect(mergeExportJobs([expired], expired, NOW)).toEqual([]);
        const history = render([], { linkedJob: expired, focusId: ID });
        expect(history.querySelector('[data-export-id]')).toBeNull();
    });

    it.each(['queued', 'running', 'retry_wait'])('keeps an active %s job when an older artifact has expired', state => {
        const active = job({
            state,
            expired: true,
            artifact: { size_bytes: 123, expires_at: new Date(NOW - 1).toISOString() },
        });
        expect(mergeExportJobs([active], active, NOW)).toEqual([active]);
        const history = render([active]);
        expect(history.querySelector('[data-export-id]')).not.toBeNull();
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
        expect(history.querySelector(`[data-export-id="${ID}"]`)).toBeNull();
        expect(history.querySelector('[data-export-retry]')).not.toBeNull();
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
        expect(render([failed]).querySelector('[data-export-retry]').disabled).toBe(false);
        expect(render([failed, job({ id: '22222222-2222-4222-8222-222222222222' })])
            .querySelector('[data-export-retry]').disabled).toBe(true);
        expect(render([failed], { busy: true }).querySelector('[data-export-retry]').disabled).toBe(true);
    });

    it('never displays a worker exception as public failed-state content', () => {
        const container = render([job({ state: 'failed', summary: { error: 'private/internal/location' } })]);
        expect(container.textContent).toContain('Export failed');
        expect(container.textContent).not.toContain('private/internal/location');
    });

    it('initializes and submits an export using only the endpoint context', async () => {
        const requests = [];
        let requested = false;
        const server = createServer((request, response) => {
            requests.push({ method: request.method, path: request.url, csrf: request.headers['x-csrftoken'] });
            if (request.method === 'POST') requested = true;
            const detail = request.url === `${ENDPOINT}${ID}/`;
            const data = request.method === 'POST' || detail
                ? job()
                : { results: requested ? [job()] : [], previous: null, next: null };
            response.writeHead(request.method === 'POST' ? 202 : 200, { 'Content-Type': 'application/json' });
            response.end(JSON.stringify(data));
        });
        await new Promise((resolve, reject) => {
            server.once('error', reject);
            server.listen(0, '127.0.0.1', resolve);
        });
        const originalUrl = window.location.href;
        const root = exportPage();
        globalThis.jsdom.reconfigure({ url: `http://127.0.0.1:${server.address().port}/exports/` });
        try {
            await init({ endpoint: ENDPOINT });
            const create = root.querySelector('#export-create');
            expect(create.disabled).toBe(false);
            root.querySelector('form').requestSubmit();
            await vi.waitFor(() => {
                expect(root.querySelector('[data-export-id]')?.dataset.exportId).toBe(ID);
                expect(root.querySelector('#export-history').getAttribute('aria-busy')).toBe('false');
            });
            expect(requests.filter(request => request.method === 'POST')).toEqual([
                { method: 'POST', path: ENDPOINT, csrf: 'export-test-csrf' },
            ]);
            expect(root.querySelector('#export-message').textContent).toContain('We will email you when it is ready.');
            expect(create.disabled).toBe(true);
        } finally {
            window.dispatchEvent(new Event('pagehide'));
            root.remove();
            globalThis.jsdom.reconfigure({ url: originalUrl });
            server.closeAllConnections();
            await new Promise(resolve => server.close(resolve));
        }
    });
});

describe('Export request and refresh budgets', () => {
    let root;
    let originalUrl;
    let fetchMock;
    let windowListeners;
    let documentListeners;

    beforeEach(() => {
        vi.useFakeTimers();
        vi.setSystemTime(NOW);
        originalUrl = window.location.href;
        globalThis.jsdom.reconfigure({ url: 'http://localhost/exports/' });
        windowListeners = vi.spyOn(window, 'addEventListener');
        documentListeners = vi.spyOn(document, 'addEventListener');
        fetchMock = vi.fn();
        vi.stubGlobal('fetch', fetchMock);
        root = exportPage();
    });

    afterEach(async () => {
        window.dispatchEvent(new Event('pagehide'));
        await vi.advanceTimersByTimeAsync(0);
        for (const [event, listener, options] of windowListeners.mock.calls) {
            if (['pagehide', 'pageshow'].includes(event)) window.removeEventListener(event, listener, options);
        }
        for (const [event, listener, options] of documentListeners.mock.calls) {
            if (event === 'visibilitychange') document.removeEventListener(event, listener, options);
        }
        root.remove();
        globalThis.jsdom.reconfigure({ url: originalUrl });
        vi.clearAllTimers();
        vi.useRealTimers();
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    it('stops after five failures with capped exponential delays', async () => {
        fetchMock.mockRejectedValue(new Error('Exports unavailable.'));
        await init({ endpoint: ENDPOINT });
        expect(fetchMock).toHaveBeenCalledTimes(1);

        for (const [index, delay] of [5000, 10_000, 20_000, 30_000].entries()) {
            await vi.advanceTimersByTimeAsync(delay - 1);
            expect(fetchMock).toHaveBeenCalledTimes(index + 1);
            await vi.advanceTimersByTimeAsync(1);
            expect(fetchMock).toHaveBeenCalledTimes(index + 2);
        }

        expect(root.querySelector('#export-message').textContent).toContain('Reload this page or try again.');
        expect(root.querySelector('#export-create').disabled).toBe(false);
        expect(vi.getTimerCount()).toBe(0);
        document.dispatchEvent(new Event('visibilitychange'));
        await vi.advanceTimersByTimeAsync(120_000);
        expect(fetchMock).toHaveBeenCalledTimes(5);
    });

    it('resets the failure budget after a successful refresh', async () => {
        fetchMock.mockRejectedValue(new Error('Exports unavailable.'))
            .mockRejectedValueOnce(new Error('Exports unavailable.'))
            .mockRejectedValueOnce(new Error('Exports unavailable.'))
            .mockResolvedValueOnce(exportResponse({ results: [job()], previous: null, next: null }));

        await init({ endpoint: ENDPOINT });
        await vi.advanceTimersByTimeAsync(5000);
        await vi.advanceTimersByTimeAsync(10_000);
        expect(fetchMock).toHaveBeenCalledTimes(3);
        expect(root.querySelector('#export-message').textContent).toBe('');
        expect(root.querySelector('#export-history').textContent).toContain('Queued');

        await vi.advanceTimersByTimeAsync(5000);
        expect(fetchMock).toHaveBeenCalledTimes(4);
        await vi.advanceTimersByTimeAsync(4999);
        expect(fetchMock).toHaveBeenCalledTimes(4);
        await vi.advanceTimersByTimeAsync(1);
        expect(fetchMock).toHaveBeenCalledTimes(5);
    });

    it('preserves the failure backoff when the page becomes visible', async () => {
        fetchMock.mockRejectedValue(new Error('Exports unavailable.'));
        await init({ endpoint: ENDPOINT });
        document.dispatchEvent(new Event('visibilitychange'));
        await vi.advanceTimersByTimeAsync(4999);
        expect(fetchMock).toHaveBeenCalledTimes(1);
        await vi.advanceTimersByTimeAsync(1);
        expect(fetchMock).toHaveBeenCalledTimes(2);
    });

    it('continues successful active-job polling beyond the failure limit', async () => {
        fetchMock.mockResolvedValue(exportResponse({ results: [job()], previous: null, next: null }));
        await init({ endpoint: ENDPOINT });
        for (let index = 0; index < 6; index += 1) {
            await vi.advanceTimersByTimeAsync(5000);
        }
        expect(fetchMock).toHaveBeenCalledTimes(7);
        expect(root.querySelector('#export-message').textContent).toBe('');
    });

    it.each(['fetch', 'body'])('times out a hanging %s even if it ignores cancellation', async stage => {
        const hanging = new Promise(() => {});
        fetchMock.mockImplementation(() => stage === 'fetch'
            ? hanging : Promise.resolve({ ok: true, json: () => hanging }));
        const url = new URL(ENDPOINT, window.location.href).href;
        const result = loadExportPage(url, url);
        const rejected = expect(result).rejects.toThrow('The export request timed out.');

        await vi.advanceTimersByTimeAsync(29_999);
        const signal = fetchMock.mock.calls[0][1].signal;
        expect(signal.aborted).toBe(false);
        await vi.advanceTimersByTimeAsync(1);
        await rejected;
        expect(signal.aborted).toBe(true);
        expect(vi.getTimerCount()).toBe(0);
    });

    it('bounds both requests when loading a linked export', async () => {
        globalThis.jsdom.reconfigure({ url: `http://localhost/exports/?export=${ID}` });
        fetchMock.mockImplementation(() => new Promise(() => {}));
        const initialized = init({ endpoint: ENDPOINT });

        await vi.advanceTimersByTimeAsync(29_999);
        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(root.querySelector('#export-history').getAttribute('aria-busy')).toBe('true');
        await vi.advanceTimersByTimeAsync(1);
        await initialized;
        expect(fetchMock.mock.calls.every(([, options]) => options.signal.aborted)).toBe(true);
        expect(root.querySelector('#export-history').getAttribute('aria-busy')).toBe('false');
        expect(root.querySelector('#export-message').textContent).toContain('timed out');
        expect(vi.getTimerCount()).toBe(1);
    });

    it('bounds rate-limit failures on the linked export even while the history succeeds', async () => {
        globalThis.jsdom.reconfigure({ url: `http://localhost/exports/?export=${ID}` });
        const linkedUrl = `http://localhost${ENDPOINT}${ID}/`;
        fetchMock.mockImplementation(url => Promise.resolve(url === linkedUrl
            ? { ok: false, status: 429, json: async () => ({ detail: 'Too many requests.' }) }
            : exportResponse({ results: [job()], previous: null, next: null })));

        await init({ endpoint: ENDPOINT });
        for (const [index, delay] of [5000, 10_000, 20_000, 30_000].entries()) {
            await vi.advanceTimersByTimeAsync(delay - 1);
            expect(fetchMock).toHaveBeenCalledTimes((index + 1) * 2);
            await vi.advanceTimersByTimeAsync(1);
            expect(fetchMock).toHaveBeenCalledTimes((index + 2) * 2);
        }

        expect(root.querySelector('#export-message').textContent).toContain('Reload this page or try again.');
        expect(root.querySelectorAll('[data-export-id]')).toHaveLength(1);
        expect(root.querySelector('#export-history').textContent).toContain('Queued');
        await vi.advanceTimersByTimeAsync(120_000);
        expect(fetchMock).toHaveBeenCalledTimes(10);
        expect(vi.getTimerCount()).toBe(0);
    });

    it.each([403, 404])('stops polling a linked export after terminal HTTP %s while history remains active', async status => {
        globalThis.jsdom.reconfigure({ url: `http://localhost/exports/?export=${ID}` });
        const linkedUrl = `http://localhost${ENDPOINT}${ID}/`;
        fetchMock.mockImplementation(url => Promise.resolve(url === linkedUrl
            ? { ok: false, status, json: async () => ({ detail: 'This export is inaccessible.' }) }
            : exportResponse({ results: [job()], previous: null, next: null })));

        await init({ endpoint: ENDPOINT });
        for (let index = 0; index < 3; index += 1) {
            await vi.advanceTimersByTimeAsync(5000);
        }

        expect(fetchMock.mock.calls.filter(([url]) => url === linkedUrl)).toHaveLength(1);
        expect(fetchMock.mock.calls.filter(([url]) => url !== linkedUrl)).toHaveLength(4);
        expect(root.querySelector('#export-message').textContent).toBe(status === 404
            ? 'This export could not be found.' : 'This export is inaccessible.');
        expect(root.querySelectorAll('[data-export-id]')).toHaveLength(1);
    });

    it('cleans up the deadline and parent listener on success or cancellation', async () => {
        const url = new URL(ENDPOINT, window.location.href).href;
        const controller = new AbortController();
        const removeListener = vi.spyOn(controller.signal, 'removeEventListener');
        fetchMock.mockResolvedValueOnce(exportResponse({ results: [] }));
        await loadExportPage(url, url, { signal: controller.signal });
        expect(removeListener).toHaveBeenCalledWith('abort', expect.any(Function));
        expect(vi.getTimerCount()).toBe(0);

        fetchMock.mockImplementation(() => new Promise(() => {}));
        const result = loadExportPage(url, url, { signal: controller.signal });
        const rejected = expect(result).rejects.toMatchObject({ name: 'AbortError' });
        await vi.advanceTimersByTimeAsync(0);
        controller.abort();
        await rejected;
        expect(fetchMock.mock.calls[1][1].signal.aborted).toBe(true);
        expect(removeListener).toHaveBeenCalledTimes(2);
        expect(vi.getTimerCount()).toBe(0);
    });

    it('cancels a hidden page request without scheduling a retry', async () => {
        fetchMock.mockImplementation(() => new Promise(() => {}));
        const initialized = init({ endpoint: ENDPOINT });
        await vi.advanceTimersByTimeAsync(0);
        window.dispatchEvent(new Event('pagehide'));
        await initialized;
        expect(root.querySelector('#export-message').textContent).toBe('');
        expect(root.querySelector('#export-history').getAttribute('aria-busy')).toBe('false');
        expect(vi.getTimerCount()).toBe(0);
        await vi.advanceTimersByTimeAsync(120_000);
        expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('times out a submission without automatically repeating the POST', async () => {
        fetchMock.mockImplementation((url, options) => options.method === 'POST'
            ? new Promise(() => {})
            : Promise.resolve(exportResponse({ results: [], previous: null, next: null })));
        await init({ endpoint: ENDPOINT });
        root.querySelector('form').requestSubmit();
        await vi.advanceTimersByTimeAsync(30_000);

        expect(root.querySelector('#export-message').textContent).toContain('timed out');
        expect(root.querySelector('#export-create').disabled).toBe(false);
        await vi.advanceTimersByTimeAsync(120_000);
        expect(fetchMock.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1);
        expect(vi.getTimerCount()).toBe(0);
    });

    it('starts a fresh refresh budget after an explicit export submission', async () => {
        fetchMock.mockRejectedValue(new Error('Exports unavailable.'));
        await init({ endpoint: ENDPOINT });
        for (const delay of [5000, 10_000, 20_000, 30_000]) {
            await vi.advanceTimersByTimeAsync(delay);
        }
        expect(root.querySelector('#export-create').disabled).toBe(false);
        fetchMock.mockClear().mockImplementation((url, options) => options.method === 'POST'
            ? Promise.resolve(exportResponse(job())) : Promise.reject(new Error('Still unavailable.')));

        root.querySelector('form').requestSubmit();
        await vi.advanceTimersByTimeAsync(0);
        expect(root.querySelector('#export-message').textContent).toBe('Still unavailable.');
        expect(fetchMock.mock.calls.filter(([, options]) => !options.method)).toHaveLength(2);
        await vi.advanceTimersByTimeAsync(5000);
        expect(fetchMock.mock.calls.filter(([, options]) => !options.method)).toHaveLength(4);
        expect(fetchMock.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1);
    });

    it('starts a fresh refresh budget after explicit pagination', async () => {
        fetchMock.mockRejectedValue(new Error('Exports unavailable.'))
            .mockResolvedValueOnce(exportResponse({ results: [], previous: null, next: `${ENDPOINT}?page=2` }));
        await init({ endpoint: ENDPOINT });
        root.querySelector('#export-next').click();
        await vi.advanceTimersByTimeAsync(0);
        for (const delay of [5000, 10_000, 20_000, 30_000]) {
            await vi.advanceTimersByTimeAsync(delay);
        }
        expect(root.querySelector('#export-message').textContent).toContain('Reload this page');
        fetchMock.mockClear();
        root.querySelector('#export-next').click();
        await vi.advanceTimersByTimeAsync(0);
        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(root.querySelector('#export-message').textContent).toBe('Exports unavailable.');
        await vi.advanceTimersByTimeAsync(5000);
        expect(fetchMock).toHaveBeenCalledTimes(2);
        fetchMock.mockResolvedValue(exportResponse({ results: [], previous: null, next: null }));
        root.querySelector('#export-next').click();
        await vi.advanceTimersByTimeAsync(0);
        expect(root.querySelector('#export-message').textContent).toBe('');
        expect(vi.getTimerCount()).toBe(0);
    });

    it('removes expired downloads after network retries are exhausted', async () => {
        const expiresAt = NOW + 70_000;
        fetchMock.mockRejectedValue(new Error('Exports unavailable.'))
            .mockResolvedValueOnce(exportResponse({
                results: [job({ state: 'ready', artifact: { expires_at: new Date(expiresAt).toISOString() } })],
                previous: null,
                next: `${ENDPOINT}?page=2`,
            }));
        await init({ endpoint: ENDPOINT });
        root.querySelector('#export-next').click();
        await vi.advanceTimersByTimeAsync(0);
        for (const delay of [5000, 10_000, 20_000, 30_000]) {
            await vi.advanceTimersByTimeAsync(delay);
        }
        expect(fetchMock).toHaveBeenCalledTimes(6);
        expect(root.querySelector('[data-export-id]')).not.toBeNull();
        await vi.advanceTimersByTimeAsync(5000);
        expect(root.querySelector('[data-export-id]')).toBeNull();
        expect(fetchMock).toHaveBeenCalledTimes(6);
        expect(vi.getTimerCount()).toBe(0);
    });
});
