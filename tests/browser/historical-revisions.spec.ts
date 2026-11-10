import { expect, test } from '@playwright/test';
import { expectRenderedFeatures, installFixture, login, waitForViewerIdle } from './viewer-fixture.ts';

test('historical revision scrubbing retains the map and settings through selection and Back', async ({ page }) => {
    const historicalUrl = process.env.VIEWER_BROWSER_HISTORICAL_URL;
    expect(historicalUrl, 'Run through the real Django browser wrapper').toBeTruthy();
    const artifactPaths = JSON.parse(process.env.VIEWER_BROWSER_HISTORICAL_ARTIFACT_PATHS || '[]') as string[];
    expect(artifactPaths, 'The wrapper supplies the exact two signed artifact paths').toHaveLength(2);
    // Storage is deliberately unavailable in browser CI. Only these two external
    // downloads are substituted; native navigation, page/controller and renderer
    // remain real. Backend pytest owns storage and authorization contracts.
    for (const [index, path] of artifactPaths.entries()) {
        const longitude = -87 + index;
        const latitude = 20 + index;
        await page.route(url => url.pathname === path, route => route.fulfill({ json: {
            type: 'FeatureCollection', features: [{
                type: 'Feature', properties: { depth: 10 },
                geometry: { type: 'LineString', coordinates: [
                    [longitude, latitude, -10], [longitude + 0.005, latitude + 0.005, -20],
                ] },
            }],
        } }));
    }
    await login(page);
    await installFixture(page, { historicalUrl: historicalUrl! });
    const project = historicalUrl!.split('/')[3]!;
    const layer = `project-layer-${project}`;
    await expectRenderedFeatures(page, layer, true);
    await waitForViewerIdle(page);
    const canvas = page.locator('canvas.maplibregl-canvas');
    const originalCanvas = await canvas.elementHandle();
    const originalWindow = await page.evaluateHandle(() => window);
    const older = page.locator('.historical-revision-list a').filter({ hasText: 'Older survey' });
    const newer = page.locator('.historical-revision-list a').filter({ hasText: 'Newer survey' });
    await expect(older).toHaveAttribute('aria-current', 'page');

    // Native manual navigation must keep its pointer gesture after movestart;
    // stopping an automatic camera flight must not cancel the user's drag.
    const initialCanvasBounds = await canvas.boundingBox();
    expect(initialCanvasBounds).not.toBeNull();
    const beforePan = await page.evaluate(() => window.__viewerEvidence.map.project([-86.9975, 20.0025]));
    const panX = initialCanvasBounds!.x + initialCanvasBounds!.width * 0.65;
    const panY = initialCanvasBounds!.y + initialCanvasBounds!.height / 2;
    await page.mouse.move(panX, panY);
    await page.mouse.down();
    await page.mouse.move(panX + 100, panY, { steps: 8 });
    await page.mouse.up();
    await waitForViewerIdle(page);
    const afterPan = await page.evaluate(() => window.__viewerEvidence.map.project([-86.9975, 20.0025]));
    expect(afterPan.x - beforePan.x).toBeGreaterThan(50);
    await expect(older).toHaveAttribute('aria-current', 'page');
    await expect(page).toHaveURL(new RegExp(`${historicalUrl!}$`));

    await page.locator('#map-settings-button').click();
    await page.getByRole('radio', { name: 'By Depth', exact: true }).check();
    await page.getByRole('button', { name: 'Close settings', exact: true }).click();
    // Drag from the selected dot itself: marker hitboxes must not swallow the
    // native range gesture, including when a longer history fills the rail.
    const firstDot = await page.locator('.revision-tick').first().boundingBox();
    const lastDot = await page.locator('.revision-tick').last().boundingBox();
    expect(firstDot).not.toBeNull();
    expect(lastDot).not.toBeNull();
    await page.mouse.move(firstDot!.x + firstDot!.width / 2, firstDot!.y + firstDot!.height / 2);
    await page.mouse.down();
    await page.mouse.move(lastDot!.x + lastDot!.width / 2, lastDot!.y + lastDot!.height / 2, { steps: 8 });
    await page.mouse.up();
    await expect(newer).toHaveAttribute('aria-current', 'page');
    await expect(page).toHaveURL(new RegExp(`${(await newer.getAttribute('href'))!}$`));
    await expectRenderedFeatures(page, `${layer}-history`, true);
    await waitForViewerIdle(page);
    expect(await originalCanvas.evaluate(element => element.isConnected)).toBe(true);
    expect(await page.evaluate(original => original === window, originalWindow)).toBe(true);
    // The surveys are geographically separated: a successful replacement must
    // refocus the same canvas so the newly selected survey is visible.
    const bounds = await canvas.boundingBox();
    expect(bounds).not.toBeNull();
    const projected = await page.evaluate(() => window.__viewerEvidence.map.project([-85.9975, 21.0025]));
    expect(projected.x).toBeGreaterThan(0);
    expect(projected.x).toBeLessThan(bounds!.width);
    expect(projected.y).toBeGreaterThan(0);
    expect(projected.y).toBeLessThan(bounds!.height);
    await page.locator('#map-settings-button').click();
    await expect(page.getByRole('radio', { name: 'By Depth', exact: true })).toBeChecked();
    await page.getByRole('button', { name: 'Close settings', exact: true }).click();

    await page.goBack();
    await expect(older).toHaveAttribute('aria-current', 'page');
    await expect(page).toHaveURL(new RegExp(`${historicalUrl!}$`));
    await expectRenderedFeatures(page, layer, true);
    await waitForViewerIdle(page);
    expect(await originalCanvas.evaluate(element => element.isConnected)).toBe(true);
    expect(await page.evaluate(original => original === window, originalWindow)).toBe(true);
    await page.locator('#map-settings-button').click();
    await expect(page.getByRole('radio', { name: 'By Depth', exact: true })).toBeChecked();
});
