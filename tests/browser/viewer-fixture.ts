import type { BrowserContext, Page, Locator } from '@playwright/test';
import type { Feature, FeatureCollection } from 'geojson';
import type { StyleSpecification } from 'maplibre-gl';
import type { EvidenceMap, ViewerEvidence } from '../../ts-types/testing/browser/viewer.ts';
import type { StationFeatureCollection } from '../../ts-types/domain/map-entities.ts';
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
    liveProvider?: boolean;
    emptyProjects?: boolean;
    providerCamera?: Pick<StyleSpecification, 'center' | 'zoom' | 'bearing' | 'pitch' | 'roll'>;
    providerAttribution?: string;
    stations?: StationFeatureCollection;
    apiResponses?: Record<string, unknown>;
    captureCanvasFrames?: boolean;
}

/** Small deterministic responses exercise real pages, controls, and MapLibre rendering. */
export async function installFixture(page: Page, { readOnly = false, publicUrl = '', liveProvider = false, emptyProjects = false, providerCamera, providerAttribution, stations, apiResponses = {}, captureCanvasFrames = false }: ViewerFixtureOptions = {}) {
    const selectedProjects = (emptyProjects ? [] : projects)
        .map(project => readOnly ? { ...project, permission: 'READ_ONLY' } : project);
    const gates = new Map<string, Promise<void>>();
    const failures = new Set<string>();
    // Observe the normal map-created event; never replace renderer or Worker methods.
    await page.addInitScript(captureFrames => {
        window.addEventListener('speleo:map-created', event => {
            const { map } = (event as CustomEvent<{ map: EvidenceMap }>).detail;
            const evidence: ViewerEvidence = { map, rendererIdle: false };
            let sequence = 0;
            window.__viewerEvidence = evidence;
            map.on('render', () => { evidence.rendererIdle = false; });
            map.on('idle', () => {
                evidence.rendererIdle = true;
                // Read the real GPU raster while its framebuffer is valid. WebKit's
                // page screenshots can retain an older composited canvas after a
                // paint-only update, even after MapLibre renders the correct pixels.
                // Only the color scenarios opt in; other tests incur no readback.
                if (captureFrames) evidence.canvasFrame = { dataUrl: map.getCanvas().toDataURL(), sequence: ++sequence };
            });
        });
    }, captureCanvasFrames);
    if (!liveProvider) await page.route('https://api.mapbox.com/styles/v1/**', route => route.fulfill({ json: {
        version: 8, glyphs: `${new URL(page.url()).origin}/viewer-fixtures/fonts/{fontstack}/{range}.pbf`,
        ...providerCamera,
        sources: providerAttribution ? { 'fixture-attribution': { type: 'geojson', data: empty, attribution: providerAttribution } } : {},
        layers: [
            { id: 'background', type: 'background', paint: { 'background-color': '#16202a' } },
            ...(providerAttribution ? [{ id: 'fixture-attribution', type: 'circle', source: 'fixture-attribution' }] : []),
        ],
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
        else if (path === '/api/v2/stations/subsurface/geojson/' && stations) data = stations;
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

/** Wait for actual map rendering before inspecting pixels or targeting canvas features. */
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

/** Assert the real rendered survey color, optionally requiring a newer completed frame. */
export async function expectGreenSurveyPixels(page: Page, visible: boolean, afterSequence = 0) {
    let sequence = afterSequence;
    const pixels = expect.poll(async () => {
        const sample = await page.evaluate(async previous => {
            const evidence = window.__viewerEvidence;
            const { map } = evidence;
            if (!evidence.rendererIdle || !map.loaded() || map.isMoving()) return null;
            const frame = evidence.canvasFrame;
            if (!frame || frame.sequence <= previous) return null;
            // Capture this immutable sample before decoding so a later idle frame
            // cannot associate an older image with a newer sequence number.
            const { dataUrl, sequence } = frame;
            const image = new Image(); image.src = dataUrl; await image.decode();
            const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
            const context = canvas.getContext('2d')!; context.drawImage(image, 0, 0);
            const values = context.getImageData(0, 0, canvas.width, canvas.height).data;
            let green = 0; let depth = 0;
            for (let index = 0; index < values.length; index += 4) {
                if (Math.abs(values[index]! - 34) < 25 && Math.abs(values[index + 1]! - 197) < 25
                    && Math.abs(values[index + 2]! - 94) < 25) green++;
                if ((Math.abs(values[index]! - 69) < 25 && Math.abs(values[index + 1]! - 117) < 25
                    && Math.abs(values[index + 2]! - 180) < 25)
                    || (Math.abs(values[index]! - 215) < 25 && Math.abs(values[index + 1]! - 48) < 25
                    && Math.abs(values[index + 2]! - 39) < 25)) depth++;
            }
            if (!evidence.rendererIdle || !map.loaded() || map.isMoving() || evidence.canvasFrame !== frame) return null;
            return { green, depth, sequence };
        }, afterSequence);
        if (sample) sequence = sample.sequence;
        // A blank framebuffer must not pass merely because it contains no green.
        if (!visible && (!sample || sample.depth <= 5)) return undefined;
        return sample?.green;
    });
    if (visible) await pixels.toBeGreaterThan(5);
    else await pixels.toBe(0);
    return sequence;
}
