import type { Page } from '@playwright/test';
import { expect, test } from '@playwright/test';
import { installFixture, login, projectId, toggleLabel } from './viewer-fixture.ts';

const browserErrors = new WeakMap<Page, string[]>();
test.beforeEach(({ page }) => {
    const errors: string[] = [];
    browserErrors.set(page, errors);
    page.on('pageerror', error => errors.push(error.message));
});
test.afterEach(({ page }) => { expect(browserErrors.get(page)).toEqual([]); });

const lineId = `project-layer-${projectId(0)}`;

async function visibility(page: Page) {
    return page.evaluate(id => window.__viewerEvidence.map.getLayoutProperty(id, 'visibility'), lineId);
}

async function changeSource(page: Page) {
    await page.getByRole('button', { name: 'Map Source', exact: true }).click();
    const radios = page.locator('#map-source-menu input[type="radio"]');
    const alternative = radios.locator('xpath=..').filter({ has: page.locator('input:not(:checked)') }).first();
    await alternative.click();
    await expect(page.locator('#map-source-button')).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator('#map-source-button')).not.toHaveAttribute('aria-busy', 'true');
}

test('public GIS loads real shared layers, limits zoom and changes display without exposing private tools', async ({ page }) => {
    const publicUrl = process.env.VIEWER_BROWSER_PUBLIC_URL;
    expect(publicUrl, 'The Django browser wrapper provides a database-only public GIS view').toBeTruthy();
    const mutations: string[] = [];
    page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/') && !['GET', 'HEAD'].includes(request.method())) mutations.push(request.url()); });
    const { requests } = await installFixture(page, { publicUrl: publicUrl! });
    await expect(page.locator('.welcome-modal-backdrop')).toBeVisible();
    await page.getByRole('button', { name: 'Close modal', exact: true }).click();
    await expect(page.locator('.welcome-modal-backdrop')).not.toBeVisible();
    expect(await page.evaluate(() => window.__viewerEvidence.map.getMaxZoom())).toBe(13);
    await expect(page.locator('#map-settings-button, #create-geometry-btn, #import-data-button, #map-managers-button, .measurement-control')).toHaveCount(0);
    expect([...requests.keys()].filter(path => path.startsWith('/api/'))).toEqual([expect.stringMatching(/^\/api\/v2\/gis-ogc\/view\/[^/]+\/geojson$/)]);

    const downloads = new Map(requests);
    const input = page.locator(`[data-project-id="${projectId(0)}"] input[type="checkbox"]`);
    await toggleLabel(input);
    await expect(input).not.toBeChecked();
    await expect.poll(() => visibility(page)).toBe('none');
    await toggleLabel(input);
    await expect.poll(() => visibility(page)).toBe('visible');
    await page.locator('#color-mode-button').click();
    await expect(page.locator('#color-mode-toggle')).toBeChecked();
    await expect.poll(() => page.evaluate(id => JSON.stringify(window.__viewerEvidence.map.getPaintProperty(id, 'line-color')), lineId)).toContain('"interpolate"');
    await changeSource(page);
    await expect.poll(() => visibility(page)).toBe('visible');
    expect(requests).toEqual(downloads);
    // Uncover the canvas point normally occupied by the project panel.
    await page.locator('#panel-toggle').click();
    await page.locator('canvas.mapboxgl-canvas').click({ button: 'right', position: { x: 100, y: 100 } });
    await expect(page.locator('#context-menu')).toHaveCount(0);
    expect(mutations).toEqual([]);
    const authoredSource = await page.request.get('/static/private/ts/map_viewer/main.ts');
    expect(authoredSource.status()).toBe(404);
});

test('read-only projects retain separate country and project visibility and disable mutation actions', async ({ page }) => {
    await login(page);
    const mutations: string[] = [];
    page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/') && !['GET', 'HEAD'].includes(request.method())) mutations.push(request.url()); });
    await installFixture(page, { readOnly: true });
    const country = page.locator('[data-country="US"] .country-toggle');
    const project = page.locator(`[data-project-id="${projectId(0)}"] input[type="checkbox"]`);
    await toggleLabel(country);
    await expect(country).not.toBeChecked();
    await expect(project).toBeChecked();
    await expect.poll(() => visibility(page)).toBe('none');
    await toggleLabel(country);
    await expect.poll(() => visibility(page)).toBe('visible');
    await toggleLabel(project);
    await expect(country).toBeChecked();
    await expect.poll(() => visibility(page)).toBe('none');
    await toggleLabel(project);
    await expect.poll(() => visibility(page)).toBe('visible');

    await page.locator('#panel-toggle').click();
    await expect.poll(() => page.evaluate(() => window.__viewerEvidence.map.isMoving())).toBe(false);
    const point = await page.evaluate(() => window.__viewerEvidence.map.project([-87, 20]));
    await page.locator('canvas.mapboxgl-canvas').click({ button: 'right', position: point });
    const menu = page.locator('#context-menu');
    await expect(menu).toBeVisible();
    const create = menu.locator('.context-menu-item').filter({ hasText: 'Create Sensor Station' });
    await expect(create).toHaveClass(/disabled/);
    await expect(create).toContainText('No write access');
    await create.click();
    await expect(page.locator('#create-station-modal')).toHaveCount(0);
    expect(mutations).toEqual([]);
});

test('map settings contain keyboard focus, restore the trigger and remain usable in fullscreen', async ({ page, browserName }) => {
    await login(page);
    await installFixture(page);
    const trigger = page.locator('#map-settings-button');
    const dialog = page.locator('#map-settings-dialog');
    await trigger.click();
    await expect(dialog).toBeVisible();
    await expect(page.locator('#map-settings-title')).toBeFocused();
    await page.locator('#create-geometry-btn').evaluate(element => (element as HTMLElement).focus());
    expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
    for (let count = 0; count < 12; count++) {
        await page.keyboard.press('Tab');
        expect(await dialog.evaluate(element => element.contains(document.activeElement))).toBe(true);
    }
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(trigger).toBeFocused();
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');

    // Mapbox hides its control where the browser does not expose fullscreen.
    const fullscreen = page.locator('.mapboxgl-ctrl-fullscreen');
    if (await page.evaluate(() => document.fullscreenEnabled)) {
        await fullscreen.click();
        await expect.poll(() => page.evaluate(() => document.fullscreenElement?.id)).toBe('map-viewer-shell');
        await trigger.click();
        await expect(dialog).toBeVisible();
        await expect(page.locator('#map-settings-title')).toBeFocused();
        await page.keyboard.press('Escape');
        if (browserName === 'webkit') {
            // WebKit consumes the first Escape to leave native fullscreen;
            // no keydown or cancel event reaches the still-focused dialog.
            await expect.poll(() => page.evaluate(() => document.fullscreenElement)).toBeNull();
            await expect(dialog).toBeVisible();
            await expect(page.locator('#map-settings-title')).toBeFocused();
            await page.keyboard.press('Escape');
        }
        await expect(dialog).not.toBeVisible();
        await expect(trigger).toBeFocused();
        if (browserName !== 'webkit') {
            await expect.poll(() => page.evaluate(() => document.fullscreenElement?.id)).toBe('map-viewer-shell');
            await page.evaluate(() => document.exitFullscreen());
        }
        await expect.poll(() => page.evaluate(() => document.fullscreenElement)).toBeNull();
    } else {
        await expect(fullscreen).not.toBeVisible();
    }
});

test('distance measurement supports keyboard placement, draft cancellation and clearing completed distances', async ({ page }) => {
    await login(page);
    await installFixture(page);
    const ruler = page.getByRole('button', { name: 'Measure distance', exact: true });
    const canvas = page.locator('canvas.mapboxgl-canvas');
    const distances = page.getByRole('list', { name: 'Completed distances' });
    const announcement = page.locator('.measurement-sr-only[role="status"]');
    await ruler.focus();
    await page.keyboard.press('Enter');
    await expect(ruler).toHaveAttribute('aria-pressed', 'true');
    await expect(canvas).toBeFocused();
    await expect(page.locator('.measurement-crosshair')).toBeVisible();
    await expect(page.getByRole('region', { name: 'Distance measurement instructions' })).toBeVisible();

    await page.keyboard.press('Enter');
    await expect(announcement).toHaveText('Measurement started. Choose where to stop measuring.');
    const originalX = await page.evaluate(() => window.__viewerEvidence.map.project([-87, 20]).x);
    await page.keyboard.press('ArrowRight');
    await expect.poll(() => page.evaluate(() => window.__viewerEvidence.map.project([-87, 20]).x)).toBeLessThan(originalX - 1);
    await page.keyboard.press('Enter');
    await expect(distances.locator('li')).toHaveCount(1);
    await expect(distances.locator('li')).toHaveText(/^Measurement 1: /);

    await page.keyboard.press('Enter');
    await expect(announcement).toHaveText('Measurement started. Choose where to stop measuring.');
    await page.keyboard.press('Escape');
    await expect(distances.locator('li')).toHaveCount(1);
    await expect(ruler).toHaveAttribute('aria-pressed', 'true');
    await ruler.click();
    await expect(ruler).toHaveAttribute('aria-pressed', 'false');
    await expect(distances.locator('li')).toHaveCount(0);
    await expect(page.locator('.measurement-crosshair')).not.toBeVisible();
    await expect(page.getByRole('region', { name: 'Distance measurement instructions' })).not.toBeVisible();
});

test('geometry drawing preserves keyboard history and draft state until explicit discard', async ({ page }) => {
    await login(page);
    await installFixture(page);
    const mutations: string[] = [];
    page.on('request', request => { if (new URL(request.url()).pathname.startsWith('/api/') && !['GET', 'HEAD'].includes(request.method())) mutations.push(request.url()); });
    const trigger = page.locator('#create-geometry-btn');
    await trigger.focus();
    await page.keyboard.press('Enter');
    const editor = page.locator('[data-geometry-editor]');
    await expect(editor).toBeVisible();
    await expect(page.getByRole('button', { name: 'Finish geometry editing to measure' })).toBeDisabled();
    await editor.getByRole('textbox', { name: 'Name', exact: true }).fill('Browser draft');
    const canvas = page.locator('canvas.mapboxgl-canvas');
    const bounds = await canvas.boundingBox();
    expect(bounds).not.toBeNull();
    // The inspector occupies the right edge; project panels occupy the left.
    const first = { x: bounds!.width * 0.4, y: bounds!.height * 0.55 };
    await canvas.click({ position: first });
    await canvas.click({ position: { x: first.x + 60, y: first.y + 25 } });
    const vertices = editor.locator('[data-editor-action="select"]');
    await expect(vertices).toHaveText('Edit 2 points');
    await expect(editor.getByRole('button', { name: 'Save geometry', exact: true })).toBeEnabled();

    await canvas.focus();
    await page.keyboard.press('Control+z');
    await expect(vertices).toHaveText('Edit 1 point');
    await expect(editor.getByRole('button', { name: 'Save geometry', exact: true })).toBeDisabled();
    await page.keyboard.press('Control+Shift+z');
    await expect(vertices).toHaveText('Edit 2 points');
    await expect(editor.getByRole('button', { name: 'Save geometry', exact: true })).toBeEnabled();
    await page.keyboard.press('Escape');
    await expect(editor).toContainText('Discard your unsaved changes?');
    await editor.getByRole('button', { name: 'Keep editing', exact: true }).click();
    await expect(editor.getByRole('textbox', { name: 'Name', exact: true })).toHaveValue('Browser draft');
    await expect(vertices).toHaveText('Edit 2 points');
    await expect(editor.getByRole('button', { name: 'Discard changes', exact: true })).not.toBeVisible();
    await editor.getByRole('button', { name: 'Close editor', exact: true }).click();
    await editor.getByRole('button', { name: 'Discard changes', exact: true }).click();
    await expect(editor).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await expect(page.getByRole('button', { name: 'Measure distance', exact: true })).toBeEnabled();
    expect(mutations).toEqual([]);
});
