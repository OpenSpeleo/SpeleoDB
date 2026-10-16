import { expect, test as base } from '@playwright/test';
import type { Locator, Page, Response } from '@playwright/test';
import { LANDMARK_ICON_OPTIONS } from '@speleodb/map-core';
import type { LandmarkIcon } from '@speleodb/map-core';
import { landmarkIconImageId } from '@speleodb/map-viewer';
import type { EvidenceMap } from '../../ts-types/testing/browser/viewer.ts';
import { BROWSER_TEST_BUDGETS } from './budgets.ts';
import { login, toggleLabel } from './viewer-fixture.ts';

const collectionColor = '#38bdf8';
const previewColor = 'rgb(56, 189, 248)';
interface SavedLandmark { id: string; name: string; icon: LandmarkIcon; collection: string }
interface OwnedRecords {
    name: string;
    collection: { id: string; name: string };
    createGeometry(): Promise<{ id: string; name: string }>;
    createLandmark(icon: LandmarkIcon, index: number): Promise<SavedLandmark>;
    readLandmark(id: string): Promise<SavedLandmark>;
}

/** Every first-party read/write is real; cleanup is restricted to this new collection. */
const test = base.extend<{ records: OwnedRecords }>({
    records: async ({ page }, use) => {
        await login(page);
        const form = await page.request.get('/private/landmark-collection/new/');
        expect(form.ok()).toBe(true);
        const csrf = (await form.text()).match(/name="csrfmiddlewaretoken" value="([^"]+)"/)?.[1];
        expect(csrf).toBeTruthy();
        const headers = { 'X-CSRFToken': csrf!, Referer: form.url() };
        const name = `GIS browser ${crypto.randomUUID()}`;
        const geometryIds: string[] = [];
        let collectionId: string | undefined;
        try {
            const created = await page.request.post('/api/v2/landmark-collections/', {
                headers, data: { name, color: collectionColor },
            });
            expect(created.status()).toBe(201);
            const collection = await created.json() as OwnedRecords['collection'];
            collectionId = collection.id;
            await use({
                name, collection,
                async createGeometry() {
                    const response = await page.request.post('/api/v2/gis-geometries/', { headers, data: {
                        name, alias: 'Entrance approach', description: 'Optional description', color: collectionColor,
                        geojson: { type: 'LineString', coordinates: [[-87.003, 20], [-86.997, 20]] },
                    } });
                    expect(response.status()).toBe(201);
                    const geometry = await response.json() as { id: string; name: string };
                    geometryIds.push(geometry.id);
                    return geometry;
                },
                async createLandmark(icon, index) {
                    const response = await page.request.post('/api/v2/landmarks/', { headers, data: {
                        name: `${name} ${icon}`, icon, collection: collection.id,
                        longitude: -87.002 + index * 0.001, latitude: 20.001,
                    } });
                    expect(response.status()).toBe(201);
                    return (await response.json() as { landmark: SavedLandmark }).landmark;
                },
                async readLandmark(id) {
                    const response = await page.request.get(`/api/v2/landmarks/${id}/`);
                    expect(response.ok()).toBe(true);
                    return (await response.json() as { landmark: SavedLandmark }).landmark;
                },
            });
        } finally {
            // Discover UI-created rows even when an assertion failed before it
            // captured their response. No pre-existing collection is touched.
            const failures: string[] = [];
            if (collectionId) {
                const listing = await page.request.get('/api/v2/landmarks/');
                if (listing.ok()) {
                    const { landmarks } = await listing.json() as { landmarks: SavedLandmark[] };
                    for (const landmark of landmarks.filter(item => item.collection === collectionId)) {
                        const response = await page.request.delete(`/api/v2/landmarks/${landmark.id}/`, { headers });
                        if (!response.ok()) failures.push(`landmark ${landmark.id}: ${response.status()}`);
                    }
                } else failures.push(`landmark listing: ${listing.status()}`);
                const response = await page.request.delete(`/api/v2/landmark-collections/${collectionId}/`, { headers });
                if (!response.ok()) failures.push(`collection ${collectionId}: ${response.status()}`);
            }
            for (const id of geometryIds) {
                const response = await page.request.delete(`/api/v2/gis-geometries/${id}/`, { headers });
                if (!response.ok()) failures.push(`geometry ${id}: ${response.status()}`);
            }
            expect(failures, 'Cleanup of test-owned GIS records').toEqual([]);
        }
    },
});

async function openViewer(page: Page) {
    const requests = new Map<string, number>();
    page.on('request', request => {
        const path = new URL(request.url()).pathname;
        requests.set(path, (requests.get(path) || 0) + 1);
    });
    // Observe the public map-created event without replacing renderer methods.
    await page.addInitScript(() => {
        window.addEventListener('speleo:map-created', event => {
            const { map } = (event as CustomEvent<{ map: EvidenceMap }>).detail;
            window.__viewerEvidence = { map, mutations: 0, sourceUpdates: 0, sourceAdds: 0, traces: [], longTasks: [], workerMessages: 0 };
        });
    });
    // External provider data is deterministic; application APIs remain untouched.
    await page.route('https://api.mapbox.com/styles/v1/**', route => route.fulfill({ headers: { 'access-control-allow-origin': '*' }, json: {
        version: 8, glyphs: 'https://api.mapbox.com/fonts/v1/mapbox/{fontstack}/{range}.pbf',
        sources: {}, layers: [{ id: 'background', type: 'background', paint: { 'background-color': '#16202a' } }],
    } }));
    await page.route('https://api.mapbox.com/fonts/v1/**', route => route.fulfill({
        body: Buffer.alloc(0), contentType: 'application/x-protobuf', headers: { 'access-control-allow-origin': '*' },
    }));
    await page.route('https://services.arcgisonline.com/**', route => route.fulfill({
        contentType: 'image/png', headers: { 'access-control-allow-origin': '*' },
        body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==', 'base64'),
    }));
    await page.goto('/private/map_viewer/');
    const hideDebugToolbar = page.getByRole('link', { name: 'Hide »', exact: true });
    if (await hideDebugToolbar.isVisible()) await hideDebugToolbar.click();
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    await page.waitForFunction(() => window.__viewerEvidence.map.loaded(), undefined, { timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    return requests;
}

async function expectImages(page: Page, icons: LandmarkIcon[]) {
    const expected = icons.map(icon => landmarkIconImageId(icon, collectionColor));
    await expect.poll(() => page.evaluate(ids => {
        const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
        return ids.filter(id => map.hasImage(id));
    }, expected)).toEqual(expected);
}

async function expectIconPreviews(dialog: Locator, color = previewColor) {
    const previews = dialog.locator('.landmark-icon-choice__preview');
    await expect(previews).toHaveCount(LANDMARK_ICON_OPTIONS.length);
    // Modal.open initializes form handlers/color after its normal setup delay.
    await expect(previews.first()).toHaveCSS('background-color', color);
    const styles = await previews.evaluateAll(async elements => Promise.all(elements.map(async element => {
        const style = getComputedStyle(element);
        const image = new Image();
        image.src = JSON.parse(style.maskImage.slice(4, -1)) as string;
        await image.decode();
        return { mask: style.maskImage, color: style.backgroundColor,
            width: element.getBoundingClientRect().width, decodedWidth: image.naturalWidth };
    })));
    for (const style of styles) {
        expect(style.mask).toMatch(/^url\(/);
        expect(style.width).toBeGreaterThan(0);
        expect(style.decodedWidth).toBeGreaterThan(0);
        expect(style.color).toBe(color);
    }
}

async function successfulWrite(page: Page, method: 'POST' | 'PATCH', action: () => Promise<unknown>) {
    const pending = page.waitForResponse(response => new URL(response.url()).pathname.startsWith('/api/v2/landmarks/')
        && response.request().method() === method);
    await action();
    const response: Response = await pending;
    expect(response.status()).toBe(method === 'POST' ? 201 : 200);
    return (await response.json() as { landmark: SavedLandmark }).landmark;
}

async function openLandmarkEditor(page: Page, records: OwnedRecords, landmark: SavedLandmark) {
    await page.getByRole('button', { name: 'Managers', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Landmarks', exact: true }).click();
    const group = page.locator(`.landmark-collection-group[data-collection-id="${records.collection.id}"]`);
    if (await group.getAttribute('open') === null) await group.locator('summary').click();
    await group.locator(`.landmark-item[data-landmark-id="${landmark.id}"]`).click();
    await expect.poll(() => page.locator('#edit-landmark-btn').evaluate(element => typeof (element as HTMLElement).onclick)).toBe('function');
    await page.locator('#edit-landmark-btn').click();
    const edit = page.locator('#edit-landmark-modal');
    await expectIconPreviews(edit);
    return edit;
}

test('geometry labels and collection-colored landmark icons survive settings and style changes', async ({ page, records }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => {
        if (message.text().includes('There is no style added to the map.')) errors.push(message.text());
    });
    const geometry = await records.createGeometry();
    for (const [index, { value }] of LANDMARK_ICON_OPTIONS.entries()) await records.createLandmark(value, index);
    const requests = await openViewer(page);
    const labelId = `gis-geometry-${geometry.id}-label`;
    await page.evaluate(() => (window.__viewerEvidence.map as unknown as import('maplibre-gl').Map)
        .jumpTo({ center: [-87, 20], zoom: 15 }));
    await page.getByRole('button', { name: 'Expand GIS Geometries', exact: true }).click();
    await toggleLabel(page.getByRole('checkbox', { name: `Show ${geometry.name}`, exact: true }));
    await expect.poll(() => page.evaluate(id => window.__viewerEvidence.map.getLayoutProperty(id, 'visibility'), labelId)).toBe('visible');
    const icons = LANDMARK_ICON_OPTIONS.map(({ value }) => value);
    await expectImages(page, icons);
    // Cold decoding must install the complete zoom sizing and collision policy.
    const markerLayout = await page.evaluate(() => (window.__viewerEvidence.map as unknown as import('maplibre-gl').Map)
        .getLayer('landmarks-layer')?.serialize().layout);
    expect(markerLayout).toMatchObject({
        'icon-size': expect.arrayContaining(['interpolate', ['zoom']]),
        'icon-allow-overlap': true, 'icon-ignore-placement': true,
        'icon-optional': true, 'text-optional': true,
    });
    expect(await page.evaluate(id => window.__viewerEvidence.map.getLayoutProperty(id, 'text-field'), labelId)).toEqual(['get', 'alias']);
    await page.locator('#map-settings-button').click();
    const labels = page.getByRole('switch', { name: 'Geometry labels', exact: true });
    await expect(labels).toBeChecked();
    await toggleLabel(labels);
    await expect.poll(() => page.evaluate(id => window.__viewerEvidence.map.getLayoutProperty(id, 'visibility'), labelId)).toBe('none');
    await page.keyboard.press('Escape');
    const detailPath = `/api/v2/gis-geometries/${geometry.id}/`;
    const detailRequests = requests.get(detailPath);
    await page.getByRole('button', { name: 'Map Source', exact: true }).click();
    await page.locator('#map-source-menu input[type="radio"]:not(:checked)').first().locator('..').click();
    await expect(page.locator('#map-source-button')).not.toHaveAttribute('aria-busy', 'true');
    await expect.poll(() => page.evaluate(id => window.__viewerEvidence.map.getLayoutProperty(id, 'visibility'), labelId)).toBe('none');
    await expectImages(page, icons);
    expect(requests.get(detailPath)).toBe(detailRequests);
    await page.reload();
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    await page.locator('#map-settings-button').click();
    await expect(page.getByRole('switch', { name: 'Geometry labels', exact: true })).not.toBeChecked();
    expect(errors).toEqual([]);
});

test('map creation and editing persist selected icons through real API writes and reload', async ({ page, records }, testInfo) => {
    // This collection initially contains only DEFAULT, so it also exercises
    // registry initialization without a custom icon in the test-owned data.
    await records.createLandmark('DEFAULT', 0);
    await openViewer(page);
    await expectImages(page, ['DEFAULT']);
    await page.getByRole('button', { name: 'Managers', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Landmarks', exact: true }).click();
    await page.locator('#create-landmark-manual-btn').click();
    const manual = page.locator('#create-landmark-manual-modal');
    await manual.locator('#landmark-collection-manual').selectOption(records.collection.id);
    await expectIconPreviews(manual);
    await manual.screenshot({ path: testInfo.outputPath('landmark-icon-picker.png') });
    await manual.locator('#landmark-name-manual').fill(`${records.name} manual`);
    await manual.locator('#landmark-latitude-manual').fill('20');
    await manual.locator('#landmark-longitude-manual').fill('-87');
    await toggleLabel(manual.getByRole('radio', { name: 'Attention', exact: true }));
    const created = await successfulWrite(page, 'POST', () => manual.getByRole('button', { name: 'Create Landmark', exact: true }).click());
    expect(created.icon).toBe('ATTENTION');
    expect(created.collection).toBe(records.collection.id);
    await expect(manual).toBeHidden();
    expect((await records.readLandmark(created.id)).icon).toBe('ATTENTION');
    await page.reload();
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    let edit = await openLandmarkEditor(page, records, created);
    await expect(edit.getByRole('radio', { name: 'Attention', exact: true })).toBeChecked();
    await edit.locator('#edit-landmark-name').fill(`${records.name} renamed`);
    const renamed = await successfulWrite(page, 'PATCH', () => edit.getByRole('button', { name: 'Save', exact: true }).click());
    expect(renamed.icon).toBe('ATTENTION');
    await expect(edit).toBeHidden();
    edit = await openLandmarkEditor(page, records, renamed);
    await toggleLabel(edit.getByRole('radio', { name: 'No go', exact: true }));
    const changed = await successfulWrite(page, 'PATCH', () => edit.getByRole('button', { name: 'Save', exact: true }).click());
    expect(changed.icon).toBe('NOGO');
    await expect(edit).toBeHidden();
    await page.reload();
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    edit = await openLandmarkEditor(page, records, changed);
    await expect(edit.getByRole('radio', { name: 'No go', exact: true })).toBeChecked();
    expect((await records.readLandmark(created.id)).icon).toBe('NOGO');
    await edit.getByRole('button', { name: 'Cancel', exact: true }).click();
    await page.locator('#landmark-details-modal').getByRole('button', { name: 'Close dialog', exact: true }).click();
    await page.evaluate(() => (window.__viewerEvidence.map as unknown as import('maplibre-gl').Map)
        .jumpTo({ center: [-87, 20], zoom: 15 }));
    await expect.poll(() => page.evaluate(() => window.__viewerEvidence.map.isMoving())).toBe(false);
    const position = await page.evaluate(() => window.__viewerEvidence.map.project([-87.005, 20.005]));
    await page.locator('canvas.maplibregl-canvas').click({ button: 'right', position });
    await page.locator('#context-menu').getByText('Create Landmark', { exact: true }).click();
    const create = page.locator('#create-landmark-modal');
    await create.locator('#landmark-collection').selectOption(records.collection.id);
    await expectIconPreviews(create);
    await create.locator('#landmark-name').fill(`${records.name} coordinate`);
    await toggleLabel(create.getByRole('radio', { name: 'Unknown', exact: true }));
    const coordinate = await successfulWrite(page, 'POST', () => create.getByRole('button', { name: 'Create', exact: true }).click());
    expect(coordinate.icon).toBe('UNKNOWN');
    expect(coordinate.collection).toBe(records.collection.id);
    await expect(create).toBeHidden();
    expect((await records.readLandmark(coordinate.id)).icon).toBe('UNKNOWN');
});

test('collection detail forms persist shared icons through creation and editing', async ({ page, records }) => {
    await page.goto(`/private/landmark-collection/${records.collection.id}/`);
    const hideDebugToolbar = page.getByRole('link', { name: 'Hide »', exact: true });
    if (await hideDebugToolbar.isVisible()) await hideDebugToolbar.click();
    await page.locator('#add-landmark-btn').click();
    const create = page.locator('#create-landmark-modal');
    await expectIconPreviews(create);
    await expect(create.getByRole('radio', { name: 'Default', exact: true })).toBeChecked();
    await create.locator('#landmark-create-form-name').fill(`${records.name} collection`);
    await create.locator('#landmark-create-form-latitude').fill('20');
    await create.locator('#landmark-create-form-longitude').fill('-87');
    await toggleLabel(create.getByRole('radio', { name: 'Cave', exact: true }));
    let reloaded = page.waitForEvent('domcontentloaded');
    const created = await successfulWrite(page, 'POST', () => create.getByRole('button', { name: 'Create Landmark', exact: true }).click());
    expect(created.icon).toBe('CAVE');
    await reloaded;
    await page.locator(`.landmark-edit-btn[data-landmark-id="${created.id}"]`).click();
    const edit = page.locator('#edit-landmark-modal');
    await expectIconPreviews(edit);
    await expect(edit.getByRole('radio', { name: 'Cave', exact: true })).toBeChecked();
    await toggleLabel(edit.getByRole('radio', { name: 'No go', exact: true }));
    reloaded = page.waitForEvent('domcontentloaded');
    const changed = await successfulWrite(page, 'PATCH', () => edit.getByRole('button', { name: 'Save', exact: true }).click());
    expect(changed.icon).toBe('NOGO');
    await reloaded;
    await page.locator(`.landmark-edit-btn[data-landmark-id="${created.id}"]`).click();
    await expect(page.locator('#edit-landmark-modal').getByRole('radio', { name: 'No go', exact: true })).toBeChecked();
    expect((await records.readLandmark(created.id)).icon).toBe('NOGO');
    await page.locator('#edit-landmark-modal').getByRole('button', { name: 'Cancel', exact: true }).click();
});
