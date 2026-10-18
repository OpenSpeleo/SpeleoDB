import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import {
    observeGestureMap, gestureFrame, gestureCanvasPoint, setGestureCamera,
    wheelToGestureZoom, installGestureSources, refreshGestureSource,
    waitForGestureSources, dragGesturePath, GESTURE_DIRECTIONS, GESTURE_AXIS_TOLERANCE,
    touchInput, pinchGesture, waitForGestureEnd, anchorGesture, observeGestureAnchor, maximumPanError,
    GESTURE_DISTANCE, GESTURE_STEPS,
} from '@speleodb/map-viewer/testing/gestures';
import type { GestureObservation } from '@speleodb/map-viewer/testing/gestures';
import { BROWSER_TEST_BUDGETS } from './budgets.ts';
import { login } from './viewer-fixture.ts';

const sourceCount = 12;
const featuresPerSource = 2000;
interface GestureEvidence {
    latitude: number;
    reducedMotion: 'reduce' | 'no-preference';
    targetZoom: number;
    delta: readonly [number, number];
    before: GestureObservation;
    path: GestureObservation[];
    maximumError: number;
}

/** Observe the production instance; keep constructors, methods and HTTP real. */
async function openViewer(page: Page, viewer: 'private' | 'public') {
    if (viewer === 'private') await login(page);
    const path = viewer === 'private' ? '/private/map_viewer/' : process.env.VIEWER_BROWSER_PUBLIC_URL;
    expect(path, 'Run through the Django browser wrapper for a real public GIS view').toBeTruthy();
    await observeGestureMap(page);
    await page.goto(path!);
    await expect(page.locator('#loading-overlay')).toBeHidden({ timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    await page.waitForFunction(() => window.__speleoGesture?.map.isStyleLoaded(), undefined,
        { timeout: BROWSER_TEST_BUDGETS.viewerStartupMs });
    const hideDebugToolbar = page.getByRole('link', { name: 'Hide »', exact: true });
    if (await hideDebugToolbar.isVisible()) await hideDebugToolbar.click();
    if (viewer === 'public') {
        const continueExploring = page.getByRole('button', { name: 'Continue Exploring', exact: true });
        await continueExploring.click();
        await expect(continueExploring).toBeHidden();
    }
    expect(await page.evaluate(() => window.__speleoGesture.map.getProjection().type)).toBe('globe');
    return gestureCanvasPoint(page, { x: 70, y: 0 });
}

for (const viewer of ['private', 'public'] as const) {
    for (const busy of [false, true]) {
        test(`${viewer} projection-crossing gestures preserve pan direction, sources=${busy}`, async ({ page }, testInfo) => {
            const errors: string[] = [];
            page.on('pageerror', error => errors.push(error.message));
            const origin = await openViewer(page, viewer);
            const evidence: GestureEvidence[] = [];
            try {
                // Pair latitude and motion rather than multiplying every case:
                // each real entrypoint/browser/workload still exercises both.
                for (const { latitude, reducedMotion } of [
                    { latitude: 20.1, reducedMotion: 'no-preference' },
                    { latitude: 46.6, reducedMotion: 'reduce' },
                ] as const) {
                    await page.emulateMedia({ reducedMotion });
                    await setGestureCamera(page, [-87.5, latitude], 12.3);
                    await gestureFrame(page);
                    if (busy) await installGestureSources(page, {
                        center: [-87.5, latitude], sourceCount, featuresPerSource,
                    });
                    // Retain gesture history across the reverse crossing and
                    // recurrence. No camera setters intervene between drags.
                    for (const targetZoom of [11.4, 12.3, 11.4]) {
                        await wheelToGestureZoom(page, origin, targetZoom);
                        for (const delta of GESTURE_DIRECTIONS) {
                            const result = await dragGesturePath(page, origin, delta, busy ? step => refreshGestureSource(page, step) : undefined);
                            evidence.push({ latitude, reducedMotion, targetZoom, delta, ...result });
                            expect(result.maximumError, JSON.stringify({ latitude, targetZoom, delta }))
                                .toBeLessThanOrEqual(GESTURE_AXIS_TOLERANCE);
                            for (const sample of result.path) {
                                expect(sample.bearing).toBeCloseTo(result.before.bearing, 6);
                                expect(sample.pitch).toBeCloseTo(result.before.pitch, 6);
                            }
                        }
                    }
                }
                const events = await page.evaluate(() => window.__speleoGesture.inputEvents);
                expect(events.wheel).toBeGreaterThanOrEqual(6);
                expect(events.drag).toBe(evidence.length);
                if (busy) await waitForGestureSources(page);
                expect(errors).toEqual([]);
            } finally {
                await testInfo.attach('gesture-paths', { contentType: 'application/json',
                    body: JSON.stringify({ evidence, errors }, null, 2) });
            }
        });
    }
}

test.describe('touch projection transitions', () => {
    test.use({ viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true });
    for (const viewer of ['private', 'public'] as const) {
        for (const reducedMotion of ['no-preference', 'reduce'] as const) {
            test(`${viewer} paused pinch handoff retains its contact (${reducedMotion})`, async ({ page, browserName }, testInfo) => {
                const errors: string[] = [];
                page.on('pageerror', error => errors.push(error.message));
                await page.emulateMedia({ reducedMotion });
                await openViewer(page, viewer);
                await setGestureCamera(page, [-87.5, 20.1], 12.3);
                await installGestureSources(page, { center: [-87.5, 20.1], sourceCount, featuresPerSource });
                const origin = await gestureCanvasPoint(page);
                const touch = await touchInput(page, browserName);
                const path: GestureObservation[] = [];
                let before: GestureObservation | undefined;
                let maximumError: number | undefined;
                try {
                    const [remainingContact, releasedContact] = await pinchGesture(touch, origin);
                    const zoom = await page.evaluate(() => window.__speleoGesture.map.getZoom());
                    expect(zoom).toBeGreaterThan(11);
                    expect(zoom).toBeLessThan(12);
                    await touch.end([releasedContact.id]);
                    // Natural camera completion must retain the held contact.
                    // A camera reset or new touchstart would hide its loss.
                    await waitForGestureEnd(page);
                    expect(await page.evaluate(() => window.__speleoGesture.map.dragPan.isActive())).toBe(true);
                    before = await anchorGesture(page, remainingContact);
                    for (let step = 1; step <= GESTURE_STEPS; step++) {
                        await refreshGestureSource(page, step);
                        await touch.move([{ ...remainingContact, y: origin.y + GESTURE_DISTANCE * step / GESTURE_STEPS }]);
                        path.push(await observeGestureAnchor(page));
                    }
                    maximumError = maximumPanError(before.point, path.map(sample => sample.point), [0, GESTURE_DISTANCE]);
                    expect(maximumError).toBeLessThanOrEqual(GESTURE_AXIS_TOLERANCE);
                    for (const sample of path) {
                        expect(sample.bearing).toBeCloseTo(before.bearing, 6);
                        expect(sample.pitch).toBeCloseTo(before.pitch, 6);
                    }
                    await touch.end([remainingContact.id]);
                    await waitForGestureEnd(page);
                    expect(await page.evaluate(() => window.__speleoGesture.map.dragPan.isActive())).toBe(false);
                    await waitForGestureSources(page);
                    expect(errors).toEqual([]);
                } finally {
                    await touch.dispose();
                    await testInfo.attach('touch-handoff-path', { contentType: 'application/json',
                        body: JSON.stringify({ reducedMotion, before, path, maximumError, errors }, null, 2) });
                }
            });
        }
    }
});
