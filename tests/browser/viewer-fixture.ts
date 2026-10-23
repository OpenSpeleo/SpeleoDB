import type { BrowserContext, Page, Locator } from '@playwright/test';
import type { Feature, FeatureCollection } from 'geojson';
import type { EvidenceMap, ViewerEvidence } from '../../ts-types/testing/browser/viewer.ts';
import { expect } from '@playwright/test';
import { BROWSER_TEST_BUDGETS } from './budgets.ts';

export const projectId = (index: number) => `10000000-0000-4000-8000-${String(index).padStart(12, '0')}`;
export const trackId = '20000000-0000-4000-8000-000000000001';
export const gisId = '30000000-0000-4000-8000-000000000001';
export const projects = Array.from({ length: 2 }, (_, index) => ({
    id: projectId(index), name: `Survey ${String(index).padStart(2, '0')}`, color: '#22c55e',
    permission: 'ADMIN', country: index === 0 ? 'US' : 'MX',
    geojson_url: `/viewer-fixtures/project-${index}.geojson`,
}));
const collection = (features: Feature[]): FeatureCollection => ({ type: 'FeatureCollection', features });
const empty = collection([]);

function survey(index: number) {
    return collection(Array.from({ length: 20 }, (_, line) => {
        const lng = -87 + index / 100 + (line % 5) / 1000;
        const lat = 20 + Math.floor(line / 5) / 1000;
        return { type: 'Feature', properties: { depth: line * 10, color: '#ff00ff' },
            geometry: { type: 'LineString', coordinates: [[lng, lat, -5], [lng + .0005, lat + .0005, -10]] } };
    }));
}

const track = collection([{ type: 'Feature', properties: {}, geometry: {
    type: 'LineString', coordinates: [[-87.001, 20.001], [-86.994, 20.002], [-86.986, 20.003]],
} }]);
const gis = collection([{ type: 'Feature', properties: { name: 'Mixed overlay' }, geometry: {
    type: 'GeometryCollection', geometries: [
        { type: 'Polygon', coordinates: [[[-87, 20], [-86.985, 20], [-86.985, 20.005], [-87, 20]]] },
        { type: 'GeometryCollection', geometries: [{ type: 'Point', coordinates: [-87, 20] }, track.features[0]!.geometry] },
    ],
} }]);

interface BrowserLoginCredentials { email: string; password: string }
const authenticatedStates = new Map<string, Awaited<ReturnType<BrowserContext['storageState']>>>();

/** Normal login creates only an authenticated browser session for the selected account. */
export async function login(page: Page, credentials: BrowserLoginCredentials = {
    email: process.env.VIEWER_BROWSER_EMAIL || 'contact@speleodb.org',
    password: process.env.VIEWER_BROWSER_PASSWORD || 'contact',
}) {
    // Reuse each account's initial real session within this Playwright worker. A new browser
    // context still keeps viewer preferences isolated between tests.
    const authenticatedState = authenticatedStates.get(credentials.email);
    if (authenticatedState) {
        await page.context().setStorageState(authenticatedState);
        return;
    }
    // An uncached account must reach the login form even after another account
    // authenticated in this context; otherwise Django redirects the existing session.
    await page.context().clearCookies();
    await page.goto('/login/');
    await page.locator('#email').fill(credentials.email);
    await page.locator('#password').fill(credentials.password);
    await page.locator('#btn_submit').click();
    await page.waitForURL('**/private/**');
    authenticatedStates.set(credentials.email, await page.context().storageState());
}

interface ViewerFixtureOptions {
    readOnly?: boolean;
    publicUrl?: string;
    emptyProjects?: boolean;
    apiResponses?: Record<string, unknown>;
}

/** Small deterministic responses exercise real pages, controls, and MapLibre rendering. */
export async function installFixture(page: Page, { readOnly = false, publicUrl = '', emptyProjects = false, apiResponses = {} }: ViewerFixtureOptions = {}) {
    const selectedProjects = (emptyProjects ? [] : projects)
        .map(project => readOnly ? { ...project, permission: 'READ_ONLY' } : project);
    const gates = new Map<string, Promise<void>>();
    const failures = new Set<string>();
    // Observe the normal map-created event; never replace renderer or Worker methods.
    await page.addInitScript(() => {
        window.addEventListener('speleo:map-created', event => {
            const { map } = (event as CustomEvent<{ map: EvidenceMap }>).detail;
            const evidence: ViewerEvidence = { map, rendererIdle: false };
            window.__viewerEvidence = evidence;
            map.on('render', () => { evidence.rendererIdle = false; });
            map.on('idle', () => { evidence.rendererIdle = true; });
        });
    });
    // The source picker keeps its real raster lifecycle; tile bytes stay local.
    await page.route(/^https:\/\/(?:services|server)\.arcgisonline\.com\/.*\/tile\//, route => route.fulfill({
        contentType: 'image/png',
        body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==', 'base64'),
    }));
    await page.route('https://api.mapbox.com/styles/v1/**', route => route.fulfill({ json: {
        version: 8, glyphs: `${new URL(page.url()).origin}/viewer-fixtures/fonts/{fontstack}/{range}.pbf`,
        sources: {},
        layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#16202a' } }],
    } }));
    await page.route('**/viewer-fixtures/**', async route => {
        const path = new URL(route.request().url()).pathname;
        if (gates.has(path)) await gates.get(path);
        if (failures.has(path)) { await route.fulfill({ status: 503, body: 'Fixture unavailable' }); return; }
        if (path.includes('/fonts/')) { await route.fulfill({ body: Buffer.alloc(0), contentType: 'application/x-protobuf' }); return; }
        const project = path.match(/project-(\d+)\.geojson/);
        await route.fulfill({ json: project ? survey(Number(project[1])) : path.endsWith('track.geojson') ? track : gis });
    });
    await page.route('**/api/v2/**', async route => {
        const path = new URL(route.request().url()).pathname;
        let data: unknown = [];
        if (Object.hasOwn(apiResponses, path)) data = apiResponses[path];
        else if (path.startsWith('/api/v2/gis-ogc/view/') && path.endsWith('/geojson')) data = { view_name: 'Browser public view', projects: selectedProjects.map(project => ({ ...project, geojson_file: project.geojson_url })) };
        else if (path === '/api/v2/projects/') data = selectedProjects;
        else if (path === '/api/v2/projects/geojson/') data = selectedProjects.map(project => ({ id: project.id, geojson_file: project.geojson_url }));
        else if (path === '/api/v2/gps_tracks/') data = [{ id: trackId, name: 'GPS route', color: '#f59e0b' }];
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
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    await page.waitForFunction(() => window.__viewerEvidence.map.loaded(), undefined, { timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    return { failures, gates };
}

/** Wait for actual map rendering before targeting canvas features with native input. */
export async function waitForViewerIdle(page: Page) {
    await expect.poll(() => page.evaluate(async () => {
        const evidence = window.__viewerEvidence;
        const settled = () => evidence.rendererIdle && evidence.map.loaded() && !evidence.map.isMoving();
        if (!settled()) return false;
        // MapLibre's idle event follows its final render submission. Leave an
        // intervening paint opportunity for software GPU/compositor work too.
        await new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
        return settled();
    }), { timeout: BROWSER_TEST_BUDGETS.assertionMs }).toBe(true);
}

export async function toggleLabel(input: Locator) {
    await input.locator('..').click();
}

/** Query rendered features, not source data or renderer configuration. */
export async function expectRenderedFeatures(page: Page, layerId: string, visible: boolean) {
    await expect.poll(() => page.evaluate(id => {
        const { map } = window.__viewerEvidence;
        if (!map.loaded() || map.isMoving()) return null;
        return Boolean(map.getLayer(id) && map.queryRenderedFeatures({ layers: [id] }).length);
    }, layerId)).toBe(visible);
}
