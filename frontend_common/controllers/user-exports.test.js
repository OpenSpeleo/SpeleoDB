import { createServer } from 'node:http';

import { renderExportHistory } from './user-exports.js';
import { mergeExportJobs } from './user-exports.js';
import { exportRefreshDelay } from './user-exports.js';
import { requestedExportId } from './user-exports.js';
import { loadExportPage } from './user-exports.js';

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

    it('gives empty-state guidance that respects export availability', () => {
        expect(render([]).textContent).toContain('Generate an export above.');
        const unavailable = render([], { canRequest: false });
        expect(unavailable.textContent).toContain('New exports are temporarily unavailable.');
        expect(unavailable.textContent).not.toContain('Generate an export above.');
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

    it('allows a failed export retry and prevents concurrent or disabled retries', () => {
        const failed = job({ state: 'failed' });
        expect(render([failed]).querySelector('[data-export-retry]').disabled).toBe(false);
        expect(render([failed, job({ id: '22222222-2222-4222-8222-222222222222' })])
            .querySelector('[data-export-retry]').disabled).toBe(true);
        expect(render([failed], { busy: true }).querySelector('[data-export-retry]').disabled).toBe(true);
        expect(render([failed], { canRequest: false }).querySelector('[data-export-retry]')).toBeNull();
    });

    it('never displays a worker exception as public failed-state content', () => {
        const container = render([job({ state: 'failed', summary: { error: 'private/internal/location' } })]);
        expect(container.textContent).toContain('Export failed');
        expect(container.textContent).not.toContain('private/internal/location');
    });
});
