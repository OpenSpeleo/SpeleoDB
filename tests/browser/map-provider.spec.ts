import { expect, test } from '@playwright/test';
import { installFixture, login } from './viewer-fixture.ts';
import { BROWSER_TEST_BUDGETS } from './budgets.ts';

// Live provider checks are explicit because they consume external provider quota.
// Deterministic suites retain intercepted provider data and run without credentials.
test.skip(process.env.VIEWER_BROWSER_LIVE_PROVIDER !== '1', 'Enable live provider verification explicitly');

test('MapLibre renders retained Mapbox imagery and vector city labels', async ({ page }) => {
    await login(page);
    await installFixture(page, { liveProvider: true });
    await expect(page.locator('.map-provider-attribution img[alt="Mapbox"]')).toBeVisible();
    await expect(page.locator('.maplibregl-ctrl-attrib')).toContainText('Mapbox');
    await expect(page.locator('.maplibregl-ctrl-attrib')).toContainText('OpenStreetMap');
    await page.evaluate(() => {
        const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
        map.jumpTo({ center: [-87.073, 20.629], zoom: 9 });
    });
    await expect.poll(() => page.evaluate(() => {
        const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
        return map.isSourceLoaded('mapbox-satellite') && map.isSourceLoaded('composite');
    }), { timeout: BROWSER_TEST_BUDGETS.viewerStartupMs }).toBe(true);
    await expect.poll(() => page.evaluate(() => {
        const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
        return map.queryRenderedFeatures({ layers: [
            'settlement-subdivision-label', 'settlement-minor-label', 'settlement-major-label',
        ] }).filter(feature => feature.geometry.type === 'Point').length;
    }), { timeout: BROWSER_TEST_BUDGETS.viewerStartupMs }).toBeGreaterThan(0);
    expect(await page.evaluate(() => {
        const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
        return map.getLayer('satellite')?.type;
    })).toBe('raster');
});
