import { expect, test } from '@playwright/test';
import { GLOBE_ATMOSPHERE_LAYER_ID } from '@speleodb/map-viewer';
import { installFixture, login } from './viewer-fixture.ts';

/** Screenshot pixels establish that the GPU produced stars and an outer rim. */
async function appearancePixels(page: import('@playwright/test').Page) {
    const screenshot = await page.locator('.maplibregl-canvas').screenshot({
        scale: 'css',
        // Element screenshots include overlapping DOM. Hide controls and the
        // public welcome dialog only during capture so they cannot count as
        // stars/atmosphere or obscure the space pixels being measured.
        style: 'body * { visibility: hidden !important; } .maplibregl-canvas { visibility: visible !important; }',
    });
    return page.evaluate(async dataUrl => {
        const image = new Image(); image.src = dataUrl; await image.decode();
        const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
        const context = canvas.getContext('2d')!; context.drawImage(image, 0, 0);
        const values = context.getImageData(0, 0, canvas.width, canvas.height).data;
        let dark = 0; let stars = 0; let halo = 0;
        for (let index = 0; index < values.length; index += 4) {
            const r = values[index]!; const g = values[index + 1]!; const b = values[index + 2]!;
            const y = Math.floor(index / 4 / canvas.width);
            if (y < canvas.height / 10) {
                if (r < 30 && g < 30 && b < 35) dark++;
                if (r > 32 && r < 100 && Math.abs(r - g) < 8 && Math.abs(r - b) < 12) stars++;
            }
            if (r > 100 && g > 100 && b > 100 && Math.max(r, g, b) - Math.min(r, g, b) < 45) halo++;
        }
        return { darkFraction: dark / (canvas.width * Math.ceil(canvas.height / 10)), stars, halo };
    }, `data:image/png;base64,${screenshot.toString('base64')}`);
}

for (const viewer of ['private', 'public'] as const) {
    test(`${viewer} globe draws stars and white atmosphere through camera and style changes`, async ({ page }, testInfo) => {
        const errors: string[] = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.setViewportSize({ width: 1200, height: 1000 });
        if (viewer === 'private') await login(page);
        const publicUrl = viewer === 'public' ? process.env.VIEWER_BROWSER_PUBLIC_URL : '';
        if (viewer === 'public') expect(publicUrl).toBeTruthy();
        await installFixture(page, { publicUrl: publicUrl || '', emptyProjects: true });
        await expect.poll(async () => (await appearancePixels(page)).halo).toBeGreaterThan(300);
        const initial = await appearancePixels(page);
        expect(initial.darkFraction).toBeGreaterThan(0.9);
        expect(initial.stars).toBeGreaterThan(20);
        await page.screenshot({ path: testInfo.outputPath(`${viewer}-globe.png`) });

        const camera = await page.evaluate(async id => {
            const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
            map.jumpTo({ center: [-73, 25], zoom: 0.5, bearing: 35, pitch: 25, padding: { left: 120, right: 0, top: 50, bottom: 0 } });
            const style = map.getStyle();
            // Custom layer instances own GPU resources and are reattached by the lifecycle.
            style.layers = style.layers.filter(layer => layer.id !== id);
            await new Promise<void>(resolve => {
                map.once('style.load', () => resolve());
                map.setStyle(style, { diff: false });
            });
            return { center: map.getCenter().toArray(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch(), present: !!map.getLayer(id) };
        }, GLOBE_ATMOSPHERE_LAYER_ID);
        expect(camera).toEqual({ center: [-73, 25], zoom: 0.5, bearing: 35, pitch: 25, present: true });
        await page.setViewportSize({ width: 1000, height: 900 });
        await expect.poll(async () => (await appearancePixels(page)).halo).toBeGreaterThan(100);
        await page.screenshot({ path: testInfo.outputPath(`${viewer}-globe-navigated.png`) });
        await page.evaluate(() => {
            const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
            map.jumpTo({ zoom: 8 });
            map.setProjection({ type: 'mercator' });
        });
        await expect.poll(async () => (await appearancePixels(page)).halo).toBe(0);
        await page.evaluate(() => {
            const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
            map.setProjection({ type: 'globe' });
            map.jumpTo({ center: [2.35, 46.6], zoom: 0, bearing: 0, pitch: 0, padding: { left: 0, right: 0, top: 0, bottom: 0 } });
        });
        await expect.poll(async () => (await appearancePixels(page)).halo).toBeGreaterThan(300);
        expect(errors).toEqual([]);
    });
}
