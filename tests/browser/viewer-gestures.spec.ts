import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import {
    observeGestureMap, gestureCanvasPoint, setGestureCamera,
    wheelToGestureZoom, dragGesturePath, GESTURE_AXIS_TOLERANCE,
    touchInput, pinchGesture, waitForGestureEnd, anchorGesture, observeGestureAnchor, maximumPanError,
    GESTURE_DISTANCE, GESTURE_STEPS,
} from '@speleodb/map-viewer/testing/gestures';
import type { GestureObservation } from '@speleodb/map-viewer/testing/gestures';
import { BROWSER_TEST_BUDGETS } from './budgets.ts';
import { installFixture, login } from './viewer-fixture.ts';

interface GestureEvidence {
    latitude: number;
    reducedMotion: 'reduce' | 'no-preference';
    targetZoom: number;
    delta: readonly [number, number];
    before: GestureObservation;
    path: GestureObservation[];
    maximumError: number;
}

/** Keep the real renderer and input handlers; supply small HTTP UI fixtures. */
async function openViewer(page: Page, viewer: 'private' | 'public') {
    if (viewer === 'private') await login(page);
    const path = viewer === 'private' ? '/private/map_viewer/' : process.env.VIEWER_BROWSER_PUBLIC_URL;
    expect(path, 'Run through the Django browser wrapper for a real public GIS view').toBeTruthy();
    await observeGestureMap(page);
    await installFixture(page, { publicUrl: viewer === 'public' ? path! : '' });
    await page.waitForFunction(() => window.__speleoGesture?.map.isStyleLoaded(), undefined,
        { timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    if (viewer === 'public') {
        const continueExploring = page.getByRole('button', { name: 'Continue Exploring', exact: true });
        await continueExploring.click();
        await expect(continueExploring).toBeHidden();
    }
    return gestureCanvasPoint(page, { x: 70, y: 0 });
}

for (const viewer of ['private', 'public'] as const) {
    test(`${viewer} projection-crossing gestures preserve pan direction`, async ({ page }, testInfo) => {
        const errors: string[] = [];
        page.on('pageerror', error => errors.push(error.message));
        const origin = await test.step('Viewer startup', () => openViewer(page, viewer));
        const evidence: GestureEvidence[] = [];
        try {
            const latitude = 20.1;
            const reducedMotion = 'no-preference';
            await test.step('Camera setup at the regression latitude with normal motion', async () => {
                await page.emulateMedia({ reducedMotion });
                await setGestureCamera(page, [-87.5, latitude], 12.3);
            });
            // Retain history across the reverse crossing and recurrence. One pan
            // per axis checks application navigation without repeating the engine's
            // direction/latitude matrix. The return crossing covers opposite signs.
            for (const [crossing, targetZoom] of [11.4, 12.3, 11.4].entries()) {
                const phase = `${crossing + 1}, target zoom ${targetZoom}`;
                await test.step(`Wheel crossing ${phase}`, () => wheelToGestureZoom(page, origin, targetZoom));
                await test.step(`Horizontal and vertical pans after crossing ${phase}`, async () => {
                    const distance = crossing === 1 ? -GESTURE_DISTANCE : GESTURE_DISTANCE;
                    for (const delta of [[distance, 0], [0, distance]] as const) {
                        const result = await dragGesturePath(page, origin, delta);
                        evidence.push({ latitude, reducedMotion, targetZoom, delta, ...result });
                        expect(result.maximumError, JSON.stringify({ latitude, targetZoom, delta }))
                            .toBeLessThanOrEqual(GESTURE_AXIS_TOLERANCE);
                        for (const sample of result.path) {
                            expect(sample.bearing).toBeCloseTo(result.before.bearing, 6);
                            expect(sample.pitch).toBeCloseTo(result.before.pitch, 6);
                        }
                    }
                });
            }
            expect(errors).toEqual([]);
        } finally {
            await testInfo.attach('gesture-paths', { contentType: 'application/json',
                body: JSON.stringify({ evidence, errors }, null, 2) });
        }
    });
}

test.describe('touch projection transitions', () => {
    test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    // Both viewers use MapCore's same touch handlers. Pair entrypoints and motion
    // preferences instead of repeating their Cartesian product in application UI tests.
    for (const { viewer, reducedMotion } of [
        { viewer: 'private', reducedMotion: 'no-preference' },
        { viewer: 'public', reducedMotion: 'reduce' },
    ] as const) {
        test(`${viewer} paused pinch handoff retains its contact (${reducedMotion})`, async ({ page, browserName }, testInfo) => {
            const errors: string[] = [];
            page.on('pageerror', error => errors.push(error.message));
            await test.step('Viewer startup', async () => {
                await page.emulateMedia({ reducedMotion });
                await openViewer(page, viewer);
            });
            const { origin, touch } = await test.step('Touch camera and input setup', async () => {
                await setGestureCamera(page, [-87.5, 20.1], 12.3);
                return { origin: await gestureCanvasPoint(page), touch: await touchInput(page, browserName) };
            });
            const path: GestureObservation[] = [];
            let before: GestureObservation | undefined;
            let maximumError: number | undefined;
            try {
                const [remainingContact, releasedContact] = await test.step('Pinch into the projection transition', async () => {
                    const contacts = await pinchGesture(touch, origin);
                    const zoom = await page.evaluate(() => window.__speleoGesture.map.getZoom());
                    expect(zoom).toBeGreaterThan(11);
                    expect(zoom).toBeLessThan(12);
                    return contacts;
                });
                await test.step('Partial release and natural completion with one contact held', async () => {
                    await touch.end([releasedContact.id]);
                    // Natural camera completion must retain the held contact.
                    // A camera reset or new touchstart would hide its loss.
                    await waitForGestureEnd(page);
                });
                await test.step('Retained-contact handoff and sampled pan', async () => {
                    before = await anchorGesture(page, remainingContact);
                    for (let step = 1; step <= GESTURE_STEPS; step++) {
                        await touch.move([{ ...remainingContact, y: origin.y + GESTURE_DISTANCE * step / GESTURE_STEPS }]);
                        path.push(await observeGestureAnchor(page));
                    }
                    maximumError = maximumPanError(before.point, path.map(sample => sample.point), [0, GESTURE_DISTANCE]);
                    expect(maximumError).toBeLessThanOrEqual(GESTURE_AXIS_TOLERANCE);
                    for (const sample of path) {
                        expect(sample.bearing).toBeCloseTo(before.bearing, 6);
                        expect(sample.pitch).toBeCloseTo(before.pitch, 6);
                    }
                });
                await test.step('Final release and natural completion', async () => {
                    await touch.end([remainingContact.id]);
                    await waitForGestureEnd(page);
                });
                expect(errors).toEqual([]);
            } finally {
                await touch.dispose();
                await testInfo.attach('touch-handoff-path', { contentType: 'application/json',
                    body: JSON.stringify({ reducedMotion, before, path, maximumError, errors }, null, 2) });
            }
        });
    }
});
