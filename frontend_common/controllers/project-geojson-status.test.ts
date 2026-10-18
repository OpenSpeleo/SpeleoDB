import type { ProjectGeoJSONStatus, ProjectGeoJSONState } from '../../ts-types/domain/project-geojson-status.ts';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { init, renderGeoJSONStatus } from './project-geojson-status.ts';
import { setBrowserUrl, startApiServer } from '../test/api-server.ts';
const projectId = '11111111-1111-4111-8111-111111111111';
const template = readFileSync('frontend_private/templates/pages/project/details.html', 'utf8');
let server: Awaited<ReturnType<typeof startApiServer>>;
let originalUrl: string;
let cleanup: (() => void) | undefined;
let root: HTMLElement;
function data(state: string = 'pending', overrides: Partial<ProjectGeoJSONStatus> = {}) { return { state: state as ProjectGeoJSONState, source_commit_sha: 'new-source', geojson_commit_sha: null, generation_commit_sha: null, geojson_revision: null, error_code: null, updated_at: null, error: '', ...overrides }; }
function visibility(hidden: boolean) { Object.defineProperty(document, 'hidden', { configurable: true, value: hidden }); document.dispatchEvent(new Event('visibilitychange')); }
beforeAll(async () => { originalUrl = window.location.href; server = await startApiServer(); });
beforeEach(() => {
    server.reset(); server.reply({ json: data() }); setBrowserUrl(`${server.origin}/project/`);
    vi.useFakeTimers(); document.body.innerHTML = template.replace(/{%.*?%}/gs, '');
    root = document.getElementById('project-geojson-status')!;
    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
});
afterEach(() => { cleanup?.(); cleanup = undefined; document.body.innerHTML = ''; vi.useRealTimers(); delete (document as unknown as { hidden?: boolean }).hidden; });
afterAll(async () => { setBrowserUrl(originalUrl); await server.close(); });
it('places the map status outside the settings form and declares the registered controller', () => {
    expect(root.closest('form, fieldset')).toBeNull();
    expect(template).toContain("vite_preload 'controller-project-geojson-status'");
    expect(template).toContain('projectId');
    const entries = JSON.parse(readFileSync(resolve('frontend_common/entries.json'), 'utf8')) as typeof import('../entries.json');
    expect(entries.scripts['controller-project-geojson-status']).toBe('frontend_common/controllers/project-geojson-status.ts');
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
    expect(root.querySelector<HTMLElement>('[data-geojson-message]')!.textContent).toBe(expected);
    expect(root.textContent).toContain('No map is currently available.');
});

it('shows a retained earlier revision and safely renders coordinate diagnostics', () => {
    const error = 'Section <img src=x onerror=alert(1)>: station FNDCO longitude -183 must be >= -180';
    renderGeoJSONStatus(root, data('failed', { geojson_commit_sha: 'old-source', error }));
    expect(root.textContent).toContain('earlier revision (old-source)');
    expect(root.querySelector<HTMLElement>('[data-geojson-error]')!.textContent).toBe(error);
    expect(root.querySelector<HTMLElement>('img')!).toBeNull();
    renderGeoJSONStatus(root, data('ready', { geojson_commit_sha: 'new-source' }));
    expect(root.textContent).toContain('Available map revision: new-source.');
    expect(root.textContent).not.toContain('earlier revision');
    expect(root.querySelector<HTMLElement>('[data-geojson-error]')!.hidden).toBe(true);
});


it('polls active work every five seconds through the generated operation and stops at ready', async () => {
    const states = ['pending', 'running', 'ready'];
    server.handle(() => ({ json: data(states.shift(), { geojson_commit_sha: states.length ? 'old-source' : 'new-source' }) }));
    cleanup = await init({ projectId });
    expect(server.requests[0]).toMatchObject({ method: 'GET', path: `/api/v2/projects/${projectId}/geojson-status/` });
    await vi.advanceTimersByTimeAsync(4999); expect(server.requests).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1); await vi.waitFor(() => expect(root.textContent).toContain('generating the map'));
    await vi.advanceTimersByTimeAsync(5000); await vi.waitFor(() => expect(root.textContent).toContain('Map ready.'));
    expect(root.textContent).toContain('Available map revision: new-source.');
    await vi.advanceTimersByTimeAsync(60_000); expect(server.requests).toHaveLength(3);
});

it.each(['failed', 'skipped', 'not_requested'])('does not poll terminal %s state on visibility changes', async state => {
    server.reply({ json: data(state) }); cleanup = await init({ projectId });
    visibility(true); visibility(false); await vi.advanceTimersByTimeAsync(60_000);
    expect(server.requests).toHaveLength(1);
});

it('pauses hidden pages and resumes on visibility and browser-back navigation', async () => {
    cleanup = await init({ projectId }); visibility(true);
    await vi.advanceTimersByTimeAsync(60_000); expect(server.requests).toHaveLength(1);
    visibility(false); await vi.waitFor(() => expect(server.requests).toHaveLength(2));
    await vi.waitFor(() => expect(root.getAttribute('aria-busy')).toBe('false'));
    window.dispatchEvent(new Event('pagehide')); await vi.advanceTimersByTimeAsync(60_000); expect(server.requests).toHaveLength(2);
    window.dispatchEvent(new Event('pageshow')); await vi.waitFor(() => expect(server.requests).toHaveLength(3));
});

it('suppresses late HTTP responses after hiding an in-flight request', async () => {
    cleanup = await init({ projectId });
    let finish!: () => void;
    server.handle(() => new Promise(resolve => { finish = () => resolve({ json: data('failed') }); }));
    await vi.advanceTimersByTimeAsync(5000); await vi.waitFor(() => expect(server.requests).toHaveLength(2));
    visibility(true); server.reply({ json: data() }); visibility(false);
    await vi.waitFor(() => expect(server.requests).toHaveLength(3)); finish();
    await vi.waitFor(() => expect(root.getAttribute('aria-busy')).toBe('false'));
    expect(root.textContent).toContain('map generation pending'); expect(root.textContent).not.toContain('map generation failed');
});

it.each([{ status: 503, json: { detail: 'Unavailable' } }, { json: { success: false } }, { text: '{broken' }])('retains the last map and retries unavailable status conservatively: %j', async failure => {
    server.reply({ json: data('pending', { geojson_commit_sha: 'old-source' }) }); cleanup = await init({ projectId });
    server.reply(failure); await vi.advanceTimersByTimeAsync(5000);
    await vi.waitFor(() => expect(root.textContent).toContain('temporarily unavailable'));
    expect(root.textContent).toContain('earlier revision (old-source)');
    server.reply({ json: data('ready') }); await vi.advanceTimersByTimeAsync(29_900); expect(server.requests).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(100); await vi.waitFor(() => expect(root.textContent).toContain('Map ready.'));
});

it('bounds hung requests with the existing 30-second budget and permits retry', async () => {
    server.handle(() => new Promise(() => {}));
    const pending = init({ projectId }); await vi.waitFor(() => expect(server.requests).toHaveLength(1));
    await vi.advanceTimersByTimeAsync(30_000); cleanup = await pending;
    expect(root.textContent).toContain('temporarily unavailable');
    server.reply({ json: data('ready') }); await vi.advanceTimersByTimeAsync(30_000);
    await vi.waitFor(() => expect(root.textContent).toContain('Map ready.')); expect(server.requests).toHaveLength(2);
});
