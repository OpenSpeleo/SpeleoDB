import { expect, test } from '@playwright/test';
import { installFixture, login } from './viewer-fixture.ts';

for (const viewer of ['private', 'public'] as const) {
    test(`${viewer} initial globe camera ignores provider metadata and preserves later navigation`, async ({ page }) => {
        const errors: string[] = [];
        page.on('pageerror', error => errors.push(error.message));
        // A viewport taller than a Mercator world tile reproduces the temporary
        // zoom clamp before the asynchronous globe style arrives.
        await page.setViewportSize({ width: 1440, height: 1100 });
        if (viewer === 'private') await login(page);
        const publicUrl = viewer === 'public' ? process.env.VIEWER_BROWSER_PUBLIC_URL : '';
        if (viewer === 'public') expect(publicUrl).toBeTruthy();
        await installFixture(page, {
            publicUrl: publicUrl || '',
            emptyProjects: true,
            providerCamera: { center: [55.13, 25.12], zoom: 12, bearing: 30, pitch: 40, roll: 15 },
        });

        const initial = await page.evaluate(() => {
            const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
            return { center: map.getCenter().toArray(), zoom: map.getZoom(),
                bearing: map.getBearing(), pitch: map.getPitch(), roll: map.getRoll(), projection: map.getProjection().type };
        });
        expect(initial.center[0]).toBeCloseTo(2.35);
        expect(initial.center[1]).toBeCloseTo(46.6);
        expect(initial.zoom).toBeCloseTo(0);
        expect(initial.bearing).toBeCloseTo(0);
        expect(initial.pitch).toBeCloseTo(0);
        expect(initial.roll).toBeCloseTo(0);
        expect(initial.projection).toBe('globe');

        const navigated = await page.evaluate(async () => {
            const map = window.__viewerEvidence.map as unknown as import('maplibre-gl').Map;
            map.jumpTo({ center: [-87.073, 20.629], zoom: 9 });
            const style = map.getStyle();
            await new Promise<void>(resolve => {
                map.once('style.load', () => resolve());
                map.setStyle(style, { diff: false });
            });
            return { center: map.getCenter().toArray(), zoom: map.getZoom() };
        });
        expect(navigated.center[0]).toBeCloseTo(-87.073);
        expect(navigated.center[1]).toBeCloseTo(20.629);
        expect(navigated.zoom).toBeCloseTo(9);
        expect(errors).toEqual([]);
    });
}
