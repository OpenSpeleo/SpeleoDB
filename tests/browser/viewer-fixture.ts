import type { BrowserContext, Page, Locator } from '@playwright/test';
import type { Feature, FeatureCollection } from 'geojson';
import type { EvidenceMapbox, ViewerEvidence, ViewerTrace } from '../../ts-types/testing/browser/viewer.ts';
import { expect } from '@playwright/test';
import { BROWSER_TEST_BUDGETS } from './budgets.ts';

export const projectId = (index: number) => `10000000-0000-4000-8000-${String(index).padStart(12, '0')}`;
export const trackId = '20000000-0000-4000-8000-000000000001';
export const gisId = '30000000-0000-4000-8000-000000000001';
export const projects = Array.from({ length: 60 }, (_, index) => ({
    id: projectId(index), name: `Survey ${String(index).padStart(2, '0')}`, color: '#22c55e',
    permission: 'ADMIN', country: index < 30 ? 'US' : 'MX',
    geojson_url: `/viewer-fixtures/project-${index}.geojson`,
}));
const collection = (features: Feature[]): FeatureCollection => ({ type: 'FeatureCollection', features });
const empty = collection([]);

function survey(index: number) {
    return collection(Array.from({ length: 2000 }, (_, line) => {
        const lng = -87 + index / 100 + line / 100000;
        const lat = 20 + line % 100 / 10000;
        return { type: 'Feature', properties: { depth: line % 200, color: '#ff00ff' },
            geometry: { type: 'LineString', coordinates: [[lng, lat, -5], [lng + .00005, lat + .00005, -10]] } };
    }));
}

const track = collection([{ type: 'Feature', properties: {}, geometry: {
    type: 'LineString', coordinates: Array.from({ length: 100_000 }, (_, index) => [-87 + index / 1000000, 20 + Math.sin(index / 1000) / 100, -123.456789012345]),
} }]);
const gis = collection([{ type: 'Feature', properties: { name: 'Mixed overlay' }, geometry: {
    type: 'GeometryCollection', geometries: [
        { type: 'Polygon', coordinates: [[[-87, 20], [-86.95, 20], [-86.95, 20.05], [-87, 20]]] },
        { type: 'GeometryCollection', geometries: [{ type: 'Point', coordinates: [-87, 20] }, track.features[0]!.geometry] },
    ],
} }]);

let authenticatedState: Awaited<ReturnType<BrowserContext['storageState']>> | undefined;

/** Normal login creates only an authenticated browser session. All viewer data is intercepted. */
export async function login(page: Page) {
    // Reuse the initial real session within this Playwright worker. Saving it
    // before application navigation keeps preferences isolated between tests.
    if (authenticatedState) {
        await page.context().setStorageState(authenticatedState);
        return;
    }
    const response = await page.request.get('/login/');
    const html = await response.text();
    const csrf = html.match(/name="csrfmiddlewaretoken" value="([^"]+)"/)?.[1];
    expect(csrf, 'Django login form CSRF token').toBeTruthy();
    const controller = JSON.parse(html.match(/data-speleodb-controller="auth-form"[^>]*>([\s\S]*?)<\/script>/)?.[1] || '{}') as {endpoint: string};
    const loggedIn = await page.request.post(controller.endpoint, { headers: { 'X-CSRFToken': csrf! }, data: {
        csrfmiddlewaretoken: csrf,
        email: process.env.VIEWER_BROWSER_EMAIL || 'contact@speleodb.org',
        password: process.env.VIEWER_BROWSER_PASSWORD || 'contact',
    } });
    expect(loggedIn.ok()).toBe(true);
    authenticatedState = await page.context().storageState();
}

/** Test-only instrumentation retains the production Mapbox renderer and map methods. */
export async function installFixture(page: Page, { stress = false, readOnly = false, publicUrl = '' } = {}) {
    const selectedProjects = (stress ? projects : projects.slice(0, 2))
        .map(project => readOnly ? { ...project, permission: 'READ_ONLY' } : project);
    const requests = new Map<string, number>();
    const gates = new Map<string, Promise<void>>();
    const failures = new Set<string>();
    await page.addInitScript(() => {
        const OriginalWorker = window.Worker;
        window.Worker = class extends OriginalWorker {
            constructor(url: string | URL, options?: WorkerOptions) {
                super(url, options);
                if (String(url).includes('geojson_worker')) this.addEventListener('message', () => {
                    if (window.__viewerEvidence) window.__viewerEvidence.workerMessages++;
                });
            }
        };
        const instrument = (library: EvidenceMapbox) => {
            // Bound renderer parallel memory in the shared development container.
            library.workerCount = 1;
            const Original = library.Map;
            library.Map = class extends Original {
                constructor(options: object) {
                    super({ ...options, style: {
                        version: 8, glyphs: `${location.origin}/viewer-fixtures/fonts/{fontstack}/{range}.pbf`,
                        sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#16202a' } }],
                    }, center: [-86.7, 20], zoom: 8, projection: 'mercator' });
                    const stats: ViewerEvidence = { map: this, mutations: 0, sourceUpdates: 0, sourceAdds: 0, traces: [], longTasks: [], workerMessages: 0 };
                    window.__viewerEvidence = stats;
                    for (const name of ['setLayoutProperty', 'setPaintProperty', 'setFilter', 'moveLayer'] as const) {
                        const original = this[name];
                        this[name] = (...args) => { stats.mutations++; return original.apply(this, args); };
                    }
                    const addSource = this.addSource;
                    this.addSource = (id: string, source: unknown) => {
                        stats.sourceAdds++;
                        const result = addSource.call(this, id, source);
                        const instance = this.getSource(id);
                        if (instance?.setData) {
                            const setData = instance.setData;
                            instance.setData = (...args) => { stats.sourceUpdates++; return setData.apply(instance, args); };
                        }
                        return result;
                    };
                    if (PerformanceObserver.supportedEntryTypes.includes('longtask')) {
                        new PerformanceObserver(list => stats.longTasks.push(...list.getEntries().map(entry => ({ duration: entry.duration, start: entry.startTime }))))
                            .observe({ type: 'longtask' });
                    }
                    document.addEventListener('change', event => {
                        if (!(event.target instanceof HTMLInputElement)) return;
                        const trace: ViewerTrace = { key: event.target.dataset.category || event.target.name || event.target.getAttribute('aria-label'), checked: event.target.checked,
                            start: performance.now(), mutations: stats.mutations };
                        stats.traces.push(trace);
                        requestAnimationFrame(() => {
                            trace.firstFrameMs = performance.now() - trace.start;
                            trace.firstFrameChecked = (event.target as HTMLInputElement).checked;
                            trace.mutationsBeforeFrame = stats.mutations - trace.mutations;
                            // A second frame follows an intervening paint opportunity;
                            // the first rAF alone runs before that opportunity.
                            requestAnimationFrame(() => {
                                trace.feedbackFrameMs = performance.now() - trace.start;
                            });
                        });
                    }, true);
                }
            };
            return library;
        };
        let library: EvidenceMapbox;
        Object.defineProperty(window, 'mapboxgl', { configurable: true,
            get: () => library, set: (value: EvidenceMapbox) => { library = instrument(value); },
        });
    });
    await page.route('**/viewer-fixtures/**', async route => {
        const path = new URL(route.request().url()).pathname;
        requests.set(path, (requests.get(path) || 0) + 1);
        if (gates.has(path)) await gates.get(path);
        if (failures.has(path)) { await route.fulfill({ status: 503, body: 'Fixture unavailable' }); return; }
        if (path.includes('/fonts/')) { await route.fulfill({ body: Buffer.alloc(0), contentType: 'application/x-protobuf' }); return; }
        const project = path.match(/project-(\d+)\.geojson/);
        await route.fulfill({ json: project ? survey(Number(project[1])) : path.endsWith('track.geojson') ? track : gis });
    });
    await page.route('**/api/v2/**', async route => {
        const path = new URL(route.request().url()).pathname;
        requests.set(path, (requests.get(path) || 0) + 1);
        let data: unknown = [];
        if (path.startsWith('/api/v2/gis-ogc/view/') && path.endsWith('/geojson')) data = { view_name: 'Browser public view', projects: selectedProjects.map(project => ({ ...project, geojson_file: project.geojson_url })) };
        else if (path === '/api/v2/projects/') data = selectedProjects;
        else if (path === '/api/v2/projects/geojson/') data = selectedProjects.map(project => ({ id: project.id, geojson_file: project.geojson_url }));
        else if (path === '/api/v2/gps_tracks/') data = [{ id: trackId, name: 'Large GPS track', color: '#f59e0b' }];
        else if (path === `/api/v2/gps_tracks/${trackId}/`) data = { id: trackId, file: '/viewer-fixtures/track.geojson' };
        else if (path === '/api/v2/gis-layers/') data = [{ id: gisId, name: 'Mixed GIS layer', color: '#6366f1' }];
        else if (path === `/api/v2/gis-layers/${gisId}/`) data = { id: gisId, file: '/viewer-fixtures/gis.geojson' };
        else if (path.includes('geojson')) data = empty;
        await route.fulfill({ json: data });
    });
    await page.goto(publicUrl || '/private/map_viewer/');
    // Use the toolbar's normal UI to uncover the top-right viewer controls.
    const hideDebugToolbar = page.getByRole('link', { name: 'Hide »', exact: true });
    if (await hideDebugToolbar.isVisible()) await hideDebugToolbar.click();
    await expect(page.locator(publicUrl ? '#color-mode-button' : '#map-settings-button')).toBeVisible();
    await expect.poll(() => page.evaluate(ids => ids.filter(id => window.__viewerEvidence?.map.getSource(`project-geojson-${id}`)).length, selectedProjects.map(project => project.id)), { timeout: BROWSER_TEST_BUDGETS.viewerStartupMs }).toBe(selectedProjects.length);
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    await page.waitForFunction(() => window.__viewerEvidence.map.loaded(), undefined, { timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    return { requests, failures, gates };
}

export async function toggleLabel(input: Locator) {
    await input.locator('..').click();
}
