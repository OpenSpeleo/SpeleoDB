import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { init, renderGeoJSONStatus } from './project-geojson-status.js';

const endpoint = '/api/v2/projects/11111111-1111-4111-8111-111111111111/geojson-status/';
const template = readFileSync(resolve('frontend_private/templates/pages/project/details.html'), 'utf8');
let cleanup;
let root;

function data(state = 'pending', overrides = {}) {
    return { state, source_commit_sha: 'new-source', geojson_commit_sha: null, error: '', ...overrides };
}
function response(state, overrides) {
    return { ok: true, json: async () => data(state, overrides) };
}
function visibility(hidden) {
    Object.defineProperty(document, 'hidden', { configurable: true, value: hidden });
    document.dispatchEvent(new Event('visibilitychange'));
}

beforeEach(() => {
    vi.useFakeTimers();
    document.body.innerHTML = template.replace(/{%.*?%}/gs, '');
    root = document.getElementById('project-geojson-status');
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response('pending')));
});

afterEach(() => {
    cleanup?.();
    cleanup = null;
    document.body.innerHTML = '';
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    delete document.hidden;
});

it('places the map status outside the settings form and declares the registered controller', () => {
    expect(root.closest('form, fieldset')).toBeNull();
    expect(template).toContain("vite_preload 'controller-project-geojson-status'");
    expect(template).toContain("url 'api:v2:project-geojson-status' id=project.id");
    const entries = JSON.parse(readFileSync(resolve('frontend_common/entries.json'), 'utf8'));
    expect(entries.scripts['controller-project-geojson-status']).toBe('frontend_common/controllers/project-geojson-status.js');
});

it.each([
    ['pending', 'Upload saved; map generation pending.'],
    ['queued', 'Upload saved; map generation pending.'],
    ['running', 'Upload saved; generating the map.'],
    ['ready', 'Map ready.'],
    ['failed', 'Upload saved; map generation failed.'],
    ['skipped', 'Upload saved; no map was generated for this revision.'],
    ['not_requested', 'No map generation requested for this revision.'],
])('renders %s without implying an upload failed', (state, expected) => {
    renderGeoJSONStatus(root, data(state));
    expect(root.querySelector('[data-geojson-message]').textContent).toBe(expected);
    expect(root.textContent).toContain('No map is currently available.');
});

it('shows a retained earlier revision and safely renders coordinate diagnostics', () => {
    const error = 'Section <img src=x onerror=alert(1)>: station FNDCO longitude -183 must be >= -180';
    renderGeoJSONStatus(root, data('failed', { geojson_commit_sha: 'old-source', error }));
    expect(root.textContent).toContain('earlier revision (old-source)');
    expect(root.querySelector('[data-geojson-error]').textContent).toBe(error);
    expect(root.querySelector('img')).toBeNull();
    renderGeoJSONStatus(root, data('ready', { geojson_commit_sha: 'new-source' }));
    expect(root.textContent).toContain('Available map revision: new-source.');
    expect(root.textContent).not.toContain('earlier revision');
    expect(root.querySelector('[data-geojson-error]').hidden).toBe(true);
});

it('polls active work every five seconds and stops at ready without another upload', async () => {
    fetch.mockResolvedValueOnce(response('pending', { geojson_commit_sha: 'old-source' }))
        .mockResolvedValueOnce(response('running', { geojson_commit_sha: 'old-source' }))
        .mockResolvedValueOnce(response('ready', { geojson_commit_sha: 'new-source', geojson_revision: 'new-artifact' }));
    cleanup = await init({ endpoint });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1]).toMatchObject({ credentials: 'same-origin' });
    await vi.advanceTimersByTimeAsync(4999);
    expect(fetch).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(root.textContent).toContain('generating the map');
    await vi.advanceTimersByTimeAsync(5000);
    expect(root.textContent).toContain('Map ready.');
    expect(root.textContent).toContain('Available map revision: new-source.');
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetch).toHaveBeenCalledTimes(3);
});

it.each(['failed', 'skipped', 'not_requested'])('does not poll terminal %s state on visibility changes', async state => {
    fetch.mockResolvedValue(response(state));
    cleanup = await init({ endpoint });
    visibility(true);
    visibility(false);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetch).toHaveBeenCalledTimes(1);
});

it('pauses hidden pages, cancels requests on navigation, and resumes after browser back', async () => {
    cleanup = await init({ endpoint });
    visibility(true);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetch).toHaveBeenCalledTimes(1);
    visibility(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(2);
    let signal;
    fetch.mockImplementationOnce((url, options) => {
        signal = options.signal;
        return new Promise((resolve, reject) => signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))));
    });
    await vi.advanceTimersByTimeAsync(5000);
    window.dispatchEvent(new Event('pagehide'));
    expect(signal.aborted).toBe(true);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(fetch).toHaveBeenCalledTimes(3);
    window.dispatchEvent(new Event('pageshow'));
    await vi.advanceTimersByTimeAsync(0);
    expect(fetch).toHaveBeenCalledTimes(4);
});

it('aborts an in-flight request on hide and ignores its late response', async () => {
    cleanup = await init({ endpoint });
    let resolveRequest;
    fetch.mockImplementationOnce(() => new Promise(resolve => { resolveRequest = resolve; }));
    await vi.advanceTimersByTimeAsync(5000);
    visibility(true);
    expect(fetch.mock.calls[1][1].signal.aborted).toBe(true);
    visibility(false);
    await vi.advanceTimersByTimeAsync(0);
    resolveRequest(response('failed'));
    await vi.advanceTimersByTimeAsync(0);
    expect(root.textContent).toContain('map generation pending');
    expect(root.textContent).not.toContain('map generation failed');
});

it.each([
    () => Promise.reject(new Error('offline')),
    () => Promise.resolve({ ok: false, status: 503 }),
    () => Promise.resolve({ ok: true, json: async () => ({ success: false }) }),
])('retries unavailable status conservatively and retains the last available map', async unavailable => {
    fetch.mockResolvedValueOnce(response('pending', { geojson_commit_sha: 'old-source' }))
        .mockImplementationOnce(unavailable)
        .mockResolvedValue(response('ready', { geojson_commit_sha: 'new-source' }));
    cleanup = await init({ endpoint });
    await vi.advanceTimersByTimeAsync(5000);
    expect(root.textContent).toContain('temporarily unavailable');
    expect(root.textContent).toContain('earlier revision (old-source)');
    await vi.advanceTimersByTimeAsync(29_999);
    expect(fetch).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(root.textContent).toContain('Map ready.');
});

it('bounds hung network requests and retries after a timeout', async () => {
    fetch.mockImplementationOnce((url, { signal }) => new Promise((resolve, reject) => {
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
    }));
    const initialized = init({ endpoint });
    await vi.advanceTimersByTimeAsync(30_000);
    cleanup = await initialized;
    expect(root.textContent).toContain('temporarily unavailable');
    await vi.advanceTimersByTimeAsync(30_000);
    expect(fetch).toHaveBeenCalledTimes(2);
});

it('rejects cross-origin status endpoints without sending a request', async () => {
    await expect(init({ endpoint: 'https://outside.example/status' })).rejects.toThrow('Invalid map status endpoint');
    expect(fetch).not.toHaveBeenCalled();
});
