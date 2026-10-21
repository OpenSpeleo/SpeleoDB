import { expect, test } from '@playwright/test';
import type { FeatureCollection } from 'geojson';
import type { GeoJSONSource } from 'maplibre-gl';
import { observeGestureMap } from '@speleodb/map-viewer/testing/gestures';
import { BROWSER_TEST_BUDGETS } from './budgets.ts';
import { login } from './viewer-fixture.ts';

interface BoundRecord {
    email: string;
    password: string;
    view_id: string;
    polygon_id: string;
    line_id: string;
    public_url: string;
    details_url: string;
    crossing_id: string;
    crossing_name: string;
    outside_id: string;
    outside_name: string;
}

test('GIS View Geographic Bound clips real stored data and can be cleared in the dashboard', async ({ page, browserName }) => {
    const records = JSON.parse(process.env.VIEWER_BROWSER_BOUND_RECORDS || '{}') as Record<string, BoundRecord>;
    const record = records[browserName];
    expect(record, 'Run through the real Django browser wrapper').toBeTruthy();
    const fixture = record!;
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    await observeGestureMap(page);
    await page.goto(fixture.public_url);
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    await expect(page.getByText(fixture.crossing_name, { exact: true })).toBeVisible();
    await expect(page.getByText(fixture.outside_name, { exact: true })).toHaveCount(0);
    const clipped = await page.evaluate(async id => {
        const source = window.__speleoGesture.map.getSource(`project-geojson-${id}`) as GeoJSONSource;
        return await source.getData() as FeatureCollection;
    }, fixture.crossing_id);
    expect(clipped.features).toHaveLength(1);
    const geometry = clipped.features[0]!.geometry;
    expect(geometry.type).toBe('LineString');
    if (geometry.type !== 'LineString') throw new Error('Expected a clipped survey line');
    expect(geometry.coordinates[0]![0]).toBeCloseTo(-87.5, 8);
    expect(geometry.coordinates.at(-1)![0]).toBeCloseTo(-87.49, 8);
    expect(await page.evaluate(id => Boolean(window.__speleoGesture.map.getSource(`project-geojson-${id}`)), fixture.outside_id)).toBe(false);

    await expect.poll(() => page.evaluate(id => {
        const map = window.__speleoGesture.map;
        return map.queryRenderedFeatures({ layers: [`gis-geometry-${id}-outline`] }).length;
    }, fixture.polygon_id)).toBeGreaterThan(0);
    const boundary = await page.evaluate(async id => {
        const map = window.__speleoGesture.map;
        const source = map.getSource(`gis-geometry-source-${id}`) as GeoJSONSource;
        return {
            data: await source.getData(),
            outline: map.getLayer(`gis-geometry-${id}-outline`)?.type,
            visibility: map.getLayoutProperty(`gis-geometry-${id}-outline`, 'visibility'),
            fill: map.getLayer(`gis-geometry-${id}-fill`)?.type,
            color: map.getPaintProperty(`gis-geometry-${id}-fill`, 'fill-color'),
            label: map.getLayer(`gis-geometry-${id}-label`)?.type,
            customBoundary: Boolean(map.getSource('gis-view-boundary')),
        };
    }, fixture.polygon_id);
    expect(boundary.data).toMatchObject({ type: 'Feature', geometry: { type: 'Polygon' } });
    expect(boundary.outline).toBe('line');
    expect(boundary.visibility).toBe('visible');
    expect(boundary.fill).toBe('fill');
    expect(boundary.color).toBe('#a855f7');
    expect(boundary.label).toBe('symbol');
    expect(boundary.customBoundary).toBe(false);

    // Real authenticated form saves exercise the nullable generated API payload.
    await login(page, { email: fixture.email, password: fixture.password });
    await page.goto(fixture.details_url);
    const selector = page.locator('#geographic_bound');
    await expect(selector).toHaveValue(fixture.polygon_id);
    await expect(selector.locator(`option[value="${fixture.line_id}"]`)).toHaveCount(0);
    await selector.selectOption('');
    const saved = page.waitForResponse(response => response.url().includes(`/user/gis_views/${fixture.view_id}/`) && response.request().method() === 'PATCH');
    await page.locator('#btn_submit').click();
    expect((await saved).ok()).toBe(true);
    await page.goto(fixture.public_url);
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    await expect(page.getByText(fixture.outside_name, { exact: true })).toBeVisible();
    const unbounded = await page.evaluate(async id => {
        const source = window.__speleoGesture.map.getSource(`project-geojson-${id}`) as GeoJSONSource;
        return await source.getData() as FeatureCollection;
    }, fixture.crossing_id);
    expect(unbounded.features).toHaveLength(2);
    expect(await page.evaluate(id => Boolean(window.__speleoGesture.map.getSource(`gis-geometry-source-${id}`)), fixture.polygon_id)).toBe(false);
    expect(errors).toEqual([]);
});
