import type { Locator, Page } from '@playwright/test';
import { expect, test } from '@playwright/test';
import type { StationFeatureCollection } from '../../ts-types/domain/map-entities.ts';
import { installFixture, login, projectId } from './viewer-fixture.ts';

const failures = new WeakMap<Page, string[]>();
test.beforeEach(({ page }) => {
    const errors: string[] = [];
    failures.set(page, errors);
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
        if (new URL(request.url()).pathname.split('/').includes('undefined')) errors.push(request.url());
    });
    page.on('response', response => {
        if (response.request().resourceType() === 'image' && !response.ok()) errors.push(`${response.status()} ${response.url()}`);
    });
    page.on('requestfailed', request => {
        if (request.resourceType() === 'image') errors.push(request.url());
    });
});
test.afterEach(({ page }) => { expect(failures.get(page)).toEqual([]); });

async function expectLoadedImages(container: Locator, count: number) {
    const images = container.locator('img');
    await expect(images).toHaveCount(count);
    await expect.poll(() => images.evaluateAll(elements => elements.every(element => {
        const image = element as HTMLImageElement;
        return Boolean(image.getAttribute('src')) && image.complete && image.naturalWidth > 0;
    }))).toBe(true);
}

test('shared icons load in survey menus, station manager and station, lead and cylinder dialogs', async ({ page }) => {
    const stationTypes = ['artifact', 'biology', 'bone', 'geology', 'sensor'];
    const stations: StationFeatureCollection = {
        type: 'FeatureCollection',
        features: stationTypes.map((type, index) => ({
            type: 'Feature', id: `40000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
            properties: { type, name: `${type} station`, project: projectId(0) },
            geometry: { type: 'Point', coordinates: [-86.99 + index / 10000, 20.005] },
        })),
    };
    await login(page);
    await installFixture(page, { stations });
    await page.getByRole('button', { name: 'Managers', exact: true }).click();
    await page.getByRole('menuitem', { name: 'Survey Stations', exact: true }).click();
    const manager = page.locator('#station-manager-modal');
    await expect(manager).toBeVisible();
    await expectLoadedImages(manager, stationTypes.length);
    await page.locator('#station-manager-close').click();
    await expect(manager).toBeHidden();

    await page.locator('#panel-toggle').click();
    const menu = page.locator('#context-menu');
    const openMenu = async () => {
        await expect.poll(() => page.evaluate(() => window.__viewerEvidence.map.isMoving())).toBe(false);
        const point = await page.evaluate(() => window.__viewerEvidence.map.project([-87, 20]));
        await page.locator('canvas.maplibregl-canvas').click({ button: 'right', position: point });
        await expect(menu).toBeVisible();
        await expectLoadedImages(menu, 7);
    };
    for (const label of ['Artifact', 'Biology', 'Bones', 'Geology', 'Sensor']) {
        await openMenu();
        await menu.locator('.context-menu-item').filter({ hasText: `Create ${label} Station` }).click();
        const dialog = page.locator('#create-station-modal');
        await expect(dialog).toBeVisible();
        await expectLoadedImages(dialog, 1);
        await dialog.getByRole('button', { name: 'Cancel', exact: true }).click();
        await expect(dialog).toBeHidden();
    }
    await openMenu();
    await menu.locator('.context-menu-item').filter({ hasText: 'Mark Exploration Lead' }).click();
    const lead = page.locator('#create-lead-modal');
    await expect(lead).toBeVisible();
    await expectLoadedImages(lead, 1);
    await lead.getByRole('button', { name: 'Cancel', exact: true }).click();
    await expect(lead).toBeHidden();

    await openMenu();
    await menu.locator('.context-menu-item').filter({ hasText: 'Install Safety Cylinder' }).click();
    const cylinder = page.locator('#cylinder-modal');
    await expect(cylinder).toBeVisible();
    await expectLoadedImages(cylinder, 2);
    await page.locator('#cylinder-modal-close').click();
    await expect(cylinder).toBeHidden();
});

test('provider credits remain after source changes without the Improve this map action', async ({ page }) => {
    const providerAttribution = [
        '<a href="https://www.mapbox.com/about/maps/">Mapbox</a>',
        '<a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        '<a class="mapbox-improve-map" href="https://www.mapbox.com/contribute/">Improve this map</a>',
        '<a class="mapbox-improve-map" href="https://example.test/survey-credit">Survey credit</a>',
    ].join(' | ');
    await login(page);
    // The source picker keeps its real raster lifecycle; tile bytes stay local.
    await page.route('https://services.arcgisonline.com/**', route => route.fulfill({
        contentType: 'image/png',
        body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLbtAAAAABJRU5ErkJggg==', 'base64'),
    }));
    await installFixture(page, { providerAttribution });
    const credits = page.locator('.maplibregl-ctrl-attrib');
    const expectCredits = async () => {
        await expect(credits.getByRole('link', { name: 'Mapbox', exact: true })).toHaveAttribute('href', 'https://www.mapbox.com/about/maps/');
        await expect(credits.getByRole('link', { name: 'OpenStreetMap', exact: true })).toHaveAttribute('href', 'https://www.openstreetmap.org/copyright');
        await expect(credits.getByRole('link', { name: 'Survey credit', exact: true })).toHaveAttribute('href', 'https://example.test/survey-credit');
        await expect(credits.getByRole('link', { name: 'Improve this map', exact: true })).toHaveCount(0);
        await expectLoadedImages(page.locator('.map-provider-attribution'), 1);
    };
    await expectCredits();
    const changeSource = async (sourceId: string) => {
        await page.getByRole('button', { name: 'Map Source', exact: true }).click();
        await page.locator(`#map-source-menu [data-source-id="${sourceId}"]`).click();
        await expect(page.locator('#map-source-button')).toHaveAttribute('aria-expanded', 'false');
        await expect(page.locator('#map-source-button')).not.toHaveAttribute('aria-busy', 'true');
        await expect.poll(() => page.evaluate(() => window.__viewerEvidence.map.loaded())).toBe(true);
    };
    await changeSource('esri-satellite');
    await expect(credits).toContainText('Sources: Esri, USGS, NOAA');
    await expect(credits.getByRole('link', { name: 'Improve this map', exact: true })).toHaveCount(0);
    await changeSource('mapbox-satellite');
    await expectCredits();
});
