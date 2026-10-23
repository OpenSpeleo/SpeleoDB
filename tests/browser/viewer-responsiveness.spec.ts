import { test, expect } from '@playwright/test';
import { expectRenderedFeatures, gisId, installFixture, login, projectId, toggleLabel, trackId } from './viewer-fixture.ts';

test.beforeEach(async ({ page }) => { await login(page); });

test('GPS loading keeps the toggle usable and displays the final selection', async ({ page }) => {
    const { gates } = await installFixture(page);
    let release!: () => void;
    gates.set('/viewer-fixtures/track.geojson', new Promise<void>(resolve => { release = resolve; }));
    await page.locator('#gps-panel-expand').click();
    const input = page.getByLabel('Show GPS route', { exact: true });
    const row = page.locator(`[data-track-id="${trackId}"]`);
    const spinner = row.locator('.gps-track-loading-spinner');
    try {
        await toggleLabel(input);
        await expect(input).toBeChecked();
        await expect(spinner).toBeVisible();
        await expect(row).toHaveAttribute('aria-busy', 'true');
        await expect(input).toBeEnabled();
        await toggleLabel(input);
        await expect(input).not.toBeChecked();
        await toggleLabel(input);
        await expect(input).toBeChecked();
    } finally {
        release();
    }
    await expect(spinner).toBeHidden();
    await expect(row).not.toHaveAttribute('aria-busy', 'true');
    await expectRenderedFeatures(page, `gps-track-line-${trackId}`, true);
    await toggleLabel(input);
    await expect(input).not.toBeChecked();
    await expectRenderedFeatures(page, `gps-track-line-${trackId}`, false);
});

test('GIS load failure permits retry and geometry toggles change the visible map', async ({ page }) => {
    const { failures } = await installFixture(page);
    failures.add('/viewer-fixtures/gis.geojson');
    await page.locator('#gis-panel-expand').click();
    const input = page.getByLabel('Show Mixed GIS layer', { exact: true });
    const row = page.locator(`[data-layer-id="${gisId}"]`);
    await toggleLabel(input);
    await expect(input).not.toBeChecked();
    await expect(input).toBeEnabled();
    await expect(row).not.toHaveAttribute('aria-busy', 'true');
    failures.delete('/viewer-fixtures/gis.geojson');
    await toggleLabel(input);
    await expect(input).toBeChecked();
    await expectRenderedFeatures(page, `gis-layer-${gisId}-fill`, true);
    await expectRenderedFeatures(page, `gis-layer-${gisId}-point`, true);
    const polygon = page.getByLabel('Show Polygon in Mixed GIS layer', { exact: true });
    await toggleLabel(polygon);
    await expect(polygon).not.toBeChecked();
    await expectRenderedFeatures(page, `gis-layer-${gisId}-fill`, false);
    await expectRenderedFeatures(page, `gis-layer-${gisId}-point`, true);
    await expectRenderedFeatures(page, `project-layer-${projectId(0)}`, true);
    await toggleLabel(polygon);
    await expect(polygon).toBeChecked();
    await expectRenderedFeatures(page, `gis-layer-${gisId}-fill`, true);
});
