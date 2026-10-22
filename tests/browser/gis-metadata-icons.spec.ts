import { expect, test } from '@playwright/test';
import type { Locator, Page } from '@playwright/test';
import { LANDMARK_ICON_OPTIONS } from '@speleodb/map-core';
import type { LandmarkIcon } from '@speleodb/map-core';
import type { FeatureCollection, Point } from 'geojson';
import { expectRenderedFeatures, installFixture, login, toggleLabel, waitForViewerIdle } from './viewer-fixture.ts';

const collectionColor = '#38bdf8';
const previewColor = 'rgb(56, 189, 248)';
const collection = {
    id: '40000000-0000-4000-8000-000000000001', name: 'Browser landmarks',
    color: collectionColor, collection_type: 'SHARED', user_permission_level: 3,
};
const geometry = {
    id: '50000000-0000-4000-8000-000000000001', name: 'Entrance approach',
    // MapLibre draws these glyphs with its local ideograph font, without a
    // network font dependency. This exercises actual alias rendering.
    alias: '入口', color: collectionColor, revision: 1, geometry_type: 'LineString',
    can_write: true, can_delete: true,
    geojson: { type: 'LineString', coordinates: [[-87.003, 20], [-86.997, 20]] },
};
function landmark(icon: LandmarkIcon, index: number) {
    return {
        id: `60000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
        name: `Browser ${icon}`, icon, collection: collection.id,
        collection_name: collection.name, collection_color: collectionColor,
        latitude: 20.001, longitude: -87.002 + index * 0.001,
        can_write: true, can_delete: true,
    };
}
function featureCollection(landmarks: ReturnType<typeof landmark>[]): FeatureCollection<Point> {
    return { type: 'FeatureCollection', features: landmarks.map(item => ({
        type: 'Feature', id: item.id, properties: item,
        geometry: { type: 'Point', coordinates: [item.longitude, item.latitude] },
    })) };
}
async function openViewer(page: Page, landmarks: ReturnType<typeof landmark>[]) {
    await login(page);
    const apiResponses: Record<string, unknown> = {
        '/api/v2/landmark-collections/': [collection],
        '/api/v2/landmarks/geojson/': featureCollection(landmarks),
        '/api/v2/gis-geometries/': [geometry],
        [`/api/v2/gis-geometries/${geometry.id}/`]: geometry,
    };
    await installFixture(page, { emptyProjects: true, apiResponses });
    await page.evaluate(() => window.__viewerEvidence.map.jumpTo({ center: [-87, 20], zoom: 15 }));
    return apiResponses;
}
async function expectIconPreviews(dialog: Locator, color = previewColor) {
    const previews = dialog.locator('.landmark-icon-choice__preview');
    await expect(previews).toHaveCount(LANDMARK_ICON_OPTIONS.length);
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
async function openManager(page: Page) {
    await page.getByRole('button', { name: 'Managers', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Landmarks', exact: true }).click();
}
/** Verify the renderer paints the collection color at every marker position. */
async function expectIconColors(page: Page) {
    const positions = await page.evaluate(points => points.map(point =>
        window.__viewerEvidence.map.project(point)),
    LANDMARK_ICON_OPTIONS.map((_, index) => [-87.002 + index * 0.001, 20.001] as [number, number]));
    const screenshot = await page.locator('.maplibregl-canvas').screenshot({
        scale: 'css',
        style: 'body * { visibility: hidden !important; } .maplibregl-canvas { visibility: visible !important; }',
    });
    const coloredPixels = await page.evaluate(async ({ dataUrl, positions }) => {
        const image = new Image(); image.src = dataUrl; await image.decode();
        const canvas = document.createElement('canvas');
        canvas.width = image.width; canvas.height = image.height;
        const context = canvas.getContext('2d')!; context.drawImage(image, 0, 0);
        return positions.map(({ x, y }) => {
            // A 40px square contains the visible symbol at this zoom. Adjacent
            // markers and the geometry's line/label fall outside that square.
            const pixels = context.getImageData(Math.round(x) - 20, Math.round(y) - 20, 40, 40).data;
            let count = 0;
            for (let index = 0; index < pixels.length; index += 4) {
                if (Math.abs(pixels[index]! - 56) < 12 && Math.abs(pixels[index + 1]! - 189) < 12
                    && Math.abs(pixels[index + 2]! - 248) < 12) count++;
            }
            return count;
        });
    }, { dataUrl: `data:image/png;base64,${screenshot.toString('base64')}`, positions });
    for (const [index, count] of coloredPixels.entries()) {
        expect(count, `${LANDMARK_ICON_OPTIONS[index]!.value} collection-colored pixels`).toBeGreaterThan(3);
    }
}
async function expectRenderedIcons(page: Page) {
    await expect.poll(() => page.evaluate(() => {
        const map = window.__viewerEvidence.map;
        if (!map.getLayer('landmarks-layer')) return [];
        return [...new Set(map.queryRenderedFeatures({ layers: ['landmarks-layer'] })
            .map(feature => feature.properties.icon as string))].sort();
    })).toEqual(LANDMARK_ICON_OPTIONS.map(({ value }) => value).sort());
}

test('geometry labels and collection-colored landmark icons remain visible across style changes', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await openViewer(page, LANDMARK_ICON_OPTIONS.map(({ value }, index) => landmark(value, index)));
    await expectRenderedIcons(page);
    await expectIconColors(page);
    await page.getByRole('button', { name: 'Expand GIS Geometries', exact: true }).click();
    await toggleLabel(page.getByRole('checkbox', { name: `Show ${geometry.name}`, exact: true }));
    const labelId = `gis-geometry-${geometry.id}-label`;
    await expectRenderedFeatures(page, labelId, true);
    await page.locator('#map-settings-button').click();
    const labels = page.getByRole('switch', { name: 'Geometry labels', exact: true });
    await expect(labels).toBeChecked();
    await toggleLabel(labels);
    await expect(labels).not.toBeChecked();
    await page.keyboard.press('Escape');
    await expectRenderedFeatures(page, labelId, false);
    await page.getByRole('button', { name: 'Map Source', exact: true }).click();
    await page.locator('#map-source-menu input[type="radio"]:not(:checked)').first().locator('..').click();
    await expect(page.locator('#map-source-button')).not.toHaveAttribute('aria-busy', 'true');
    await expectRenderedIcons(page);
    await expectIconColors(page);
    await expectRenderedFeatures(page, labelId, false);
    await page.locator('#map-settings-button').click();
    await expect(labels).not.toBeChecked();
    await toggleLabel(labels);
    await page.keyboard.press('Escape');
    await expectRenderedFeatures(page, labelId, true);
    expect(errors).toEqual([]);
});

test('map landmark forms show icon selection, errors and successful completion', async ({ page }) => {
    // Editing begins with independent input, never with a previous write's result.
    const existing = landmark('CAVE', 0);
    const manualResult = { ...landmark('ATTENTION', 1), name: 'Manual landmark' };
    const coordinateResult = { ...landmark('UNKNOWN', 2), name: 'Coordinate landmark' };
    const apiResponses = await openViewer(page, [existing]);
    const edited = { ...existing, name: 'Updated cave', icon: 'NOGO' as const };
    let currentExisting = existing;
    let createResult = manualResult;
    let fail = false;
    await page.route('**/api/v2/landmarks/**', async route => {
        if (route.request().method() === 'GET') { await route.fallback(); return; }
        if (fail) { await route.fulfill({ status: 400, json: { detail: 'Choose a different location' } }); return; }
        const updating = route.request().method() === 'PATCH';
        if (updating) currentExisting = edited;
        apiResponses['/api/v2/landmarks/geojson/'] = featureCollection([currentExisting, createResult]);
        await route.fulfill({ status: updating ? 200 : 201,
            json: { landmark: updating ? edited : createResult } });
    });
    await openManager(page);
    await page.locator('#create-landmark-manual-btn').click();
    const manual = page.locator('#create-landmark-manual-modal');
    await manual.locator('#landmark-collection-manual').selectOption(collection.id);
    await expectIconPreviews(manual);
    await manual.locator('#landmark-name-manual').fill(manualResult.name);
    await manual.locator('#landmark-latitude-manual').fill('20');
    await manual.locator('#landmark-longitude-manual').fill('-87');
    await toggleLabel(manual.getByRole('radio', { name: 'Attention', exact: true }));
    await expect(manual.getByRole('radio', { name: 'Attention', exact: true })).toBeChecked();
    await manual.getByRole('button', { name: 'Create Landmark', exact: true }).click();
    await expect(manual).toBeHidden();
    await expect(page.getByText('Landmark created!', { exact: true })).toBeVisible();

    await openManager(page);
    const group = page.locator(`.landmark-collection-group[data-collection-id="${collection.id}"]`);
    if (await group.getAttribute('open') === null) await group.locator('summary').click();
    await group.locator(`.landmark-item[data-landmark-id="${existing.id}"]`).click();
    await expect(page.locator('#edit-landmark-btn')).toBeEnabled();
    await page.locator('#edit-landmark-btn').click();
    const edit = page.locator('#edit-landmark-modal');
    await expectIconPreviews(edit);
    await expect(edit.getByRole('radio', { name: 'Cave', exact: true })).toBeChecked();
    await edit.locator('#edit-landmark-name').fill(edited.name);
    await toggleLabel(edit.getByRole('radio', { name: 'No go', exact: true }));
    await expect(edit.getByRole('radio', { name: 'No go', exact: true })).toBeChecked();
    await edit.getByRole('button', { name: 'Save', exact: true }).click();
    await expect(edit).toBeHidden();
    await expect(page.getByText('Landmark updated', { exact: true })).toBeVisible();
    await openManager(page);
    if (await group.getAttribute('open') === null) await group.locator('summary').click();
    await expect(group.locator(`.landmark-item[data-landmark-id="${existing.id}"]`)).toContainText(edited.name);
    await page.locator('#landmark-manager-close').click();

    createResult = coordinateResult;
    await waitForViewerIdle(page);
    const canvas = page.locator('canvas.maplibregl-canvas');
    const bounds = await canvas.boundingBox();
    expect(bounds).not.toBeNull();
    // Any empty visible position exercises coordinate creation. A fixed world
    // coordinate can leave the viewport after the editor's automatic fly-to.
    await canvas.click({ button: 'right', position: { x: bounds!.width * 0.7, y: bounds!.height * 0.6 } });
    await page.locator('#context-menu').getByText('Create Landmark', { exact: true }).click();
    const create = page.locator('#create-landmark-modal');
    await create.locator('#landmark-collection').selectOption(collection.id);
    await expectIconPreviews(create);
    await create.locator('#landmark-name').fill(coordinateResult.name);
    await toggleLabel(create.getByRole('radio', { name: 'Unknown', exact: true }));
    await expect(create.getByRole('radio', { name: 'Unknown', exact: true })).toBeChecked();
    fail = true;
    await create.getByRole('button', { name: 'Create', exact: true }).click();
    await expect(page.getByText('Choose a different location', { exact: true })).toBeVisible();
    await expect(create).toBeVisible();
    fail = false;
    await create.getByRole('button', { name: 'Create', exact: true }).click();
    await expect(create).toBeHidden();
    await expect(page.locator('#landmark-details-modal')).toContainText(coordinateResult.name);
});

test('collection detail icon forms show existing selection, errors and completion navigation', async ({ page }) => {
    await login(page);
    const routes = JSON.parse(process.env.VIEWER_BROWSER_ROUTES || '{}') as { writable_landmarks?: string };
    expect(routes.writable_landmarks, 'Run through tests/browser/test_django_browser.py').toBeTruthy();
    await page.goto(routes.writable_landmarks!);
    const hideDebugToolbar = page.getByRole('link', { name: 'Hide »', exact: true });
    if (await hideDebugToolbar.isVisible()) await hideDebugToolbar.click();
    let fail = true;
    await page.route('**/api/v2/landmarks/**', route => route.fulfill(fail
        ? { status: 400, json: { detail: 'Choose a different location' } }
        : { status: route.request().method() === 'POST' ? 201 : 200,
            json: { landmark: { id: '60000000-0000-4000-8000-000000000010' } } }));
    await page.locator('#add-landmark-btn').click();
    const create = page.locator('#create-landmark-modal');
    await expectIconPreviews(create);
    await expect(create.getByRole('radio', { name: 'Default', exact: true })).toBeChecked();
    await create.locator('#landmark-create-form-name').fill('Collection landmark');
    await create.locator('#landmark-create-form-latitude').fill('20');
    await create.locator('#landmark-create-form-longitude').fill('-87');
    await toggleLabel(create.getByRole('radio', { name: 'Cave', exact: true }));
    await expect(create.getByRole('radio', { name: 'Cave', exact: true })).toBeChecked();
    await create.getByRole('button', { name: 'Create Landmark', exact: true }).click();
    await expect(create.locator('#landmark-create-error')).toContainText('Choose a different location');
    await expect(create.locator('#landmark-create-form-name')).toHaveValue('Collection landmark');
    fail = false;
    await Promise.all([page.waitForEvent('domcontentloaded'),
        create.getByRole('button', { name: 'Create Landmark', exact: true }).click()]);
    await expect(create).toHaveCount(0);
    // The server-rendered row is seeded independently; this checks editing UI,
    // not whether the intercepted create persisted anything.
    await page.locator('.landmark-edit-btn').click();
    const edit = page.locator('#edit-landmark-modal');
    await expectIconPreviews(edit);
    await expect(edit.getByRole('radio', { name: 'Cave', exact: true })).toBeChecked();
    await toggleLabel(edit.getByRole('radio', { name: 'No go', exact: true }));
    await expect(edit.getByRole('radio', { name: 'No go', exact: true })).toBeChecked();
    await Promise.all([page.waitForEvent('domcontentloaded'),
        edit.getByRole('button', { name: 'Save', exact: true }).click()]);
    await expect(edit).toHaveCount(0);
    await expect(page.locator('#collection_landmarks_table')).toBeVisible();
});
